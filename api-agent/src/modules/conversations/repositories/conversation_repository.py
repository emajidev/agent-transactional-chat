import logging
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import ProgrammingError

from src.common.enums.conversation_status import ConversationStatus
from src.common.repositories import BaseRepository
from src.common.resilience import retry_db_operation
from src.modules.conversations.dtos.conversation import ConversationCreate, ConversationUpdate
from src.modules.conversations.entities import Conversation

logger = logging.getLogger(__name__)


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    @retry_db_operation(max_attempts=3, initial_wait=0.5, max_wait=5.0)
    def get_by_id(self, conversation_id: int) -> Conversation | None:
        # Verificar si hay campos de estado que no existen
        existing_columns = self._get_existing_columns()
        state_fields = {'recipient_phone', 'amount', 'currency', 'confirmation_pending', 'transaction_id'}
        missing_state_fields = [field for field in state_fields if field not in existing_columns]
        
        # Si hay campos que no existen, usar SQL raw
        if missing_state_fields:
            logger.debug(f"Usando SQL raw para get_by_id porque faltan campos: {missing_state_fields}")
            table = Conversation.__table__
            # Construir SELECT con solo campos que existen
            basic_columns = ['id', 'user_id', 'started_at', 'ended_at', 'status', 'created_at', 'updated_at', 'deleted_at']
            columns_to_select = [col for col in basic_columns if col in existing_columns]
            columns_str = ', '.join([f'{table.name}.{col}' for col in columns_to_select])
            
            sql_select = f"""
                SELECT {columns_str}
                FROM {table.name}
                WHERE {table.name}.id = :conversation_id 
                AND {table.name}.deleted_at IS NULL
                LIMIT 1
            """
            
            try:
                result = self.session.execute(sa.text(sql_select), {'conversation_id': conversation_id})
                row_data = result.fetchone()
                
                if row_data:
                    # Crear un objeto Conversation manualmente con los datos
                    data_dict = dict(zip(columns_to_select, row_data))
                    db_conversation = Conversation()
                    for key, value in data_dict.items():
                        if hasattr(Conversation, key):
                            setattr(db_conversation, key, value)
                    return db_conversation
                else:
                    return None
            except ProgrammingError as e:
                logger.warning(f"Error en get_by_id con SQL raw: {str(e)}")
                return None
        else:
            # Si todos los campos existen, usar el query normal
            try:
                return (
                    self.session.query(Conversation)
                    .filter(Conversation.id == conversation_id)
                    .filter(Conversation.deleted_at.is_(None))
                    .first()
                )
            except ProgrammingError as e:
                # Si falla, intentar con SQL raw como fallback
                if "column" in str(e).lower() or "does not exist" in str(e).lower():
                    logger.debug(f"Query falló en get_by_id, usando SQL raw como fallback: {str(e)}")
                    try:
                        self.session.rollback()
                    except Exception:
                        pass
                    
                    table = Conversation.__table__
                    basic_columns = ['id', 'user_id', 'started_at', 'ended_at', 'status', 'created_at', 'updated_at', 'deleted_at']
                    columns_to_select = [col for col in basic_columns if col in existing_columns]
                    columns_str = ', '.join([f'{table.name}.{col}' for col in columns_to_select])
                    
                    sql_select = f"""
                        SELECT {columns_str}
                        FROM {table.name}
                        WHERE {table.name}.id = :conversation_id 
                        AND {table.name}.deleted_at IS NULL
                        LIMIT 1
                    """
                    
                    result = self.session.execute(sa.text(sql_select), {'conversation_id': conversation_id})
                    row_data = result.fetchone()
                    
                    if row_data:
                        data_dict = dict(zip(columns_to_select, row_data))
                        db_conversation = Conversation()
                        for key, value in data_dict.items():
                            if hasattr(Conversation, key):
                                setattr(db_conversation, key, value)
                        return db_conversation
                    else:
                        return None
                else:
                    raise

    def get_all(
        self,
        skip: int = 0,
        limit: int = 100,
        filters: dict[str, Any] | None = None,
    ) -> list[Conversation]:
        # El filtrado por deleted_at se hace automáticamente en _build_query del BaseRepository
        return super().get_all(skip=skip, limit=limit, filters=filters)

    def _get_existing_columns(self) -> set[str]:
        """Obtiene las columnas que existen en la tabla conversations."""
        try:
            inspector = sa.inspect(self.session.bind)
            columns = inspector.get_columns('conversations')
            return {col['name'] for col in columns}
        except Exception as e:
            logger.warning(f"Error al obtener columnas de la tabla: {str(e)}")
            # Retornar columnas básicas si hay error
            return {'id', 'user_id', 'started_at', 'ended_at', 'status', 'created_at', 'updated_at', 'deleted_at'}

    def create(self, conversation_data: ConversationCreate) -> Conversation:
        # Convertir el enum a su valor antes de crear la entidad
        # Usar model_dump con mode='python' para obtener valores nativos
        data = conversation_data.model_dump(mode="python", exclude_unset=True)

        # Establecer started_at si no se proporciona
        if "started_at" not in data:
            data["started_at"] = datetime.now(UTC)

        # Asegurar que el status sea el valor del enum (string)
        if "status" in data:
            if isinstance(data["status"], ConversationStatus):
                data["status"] = data["status"].value
            elif isinstance(data["status"], str):
                # Si ya es string, verificar que sea válido
                data["status"] = data["status"].lower()

        # Filtrar campos que no existen en la tabla
        existing_columns = self._get_existing_columns()
        # Campos de estado que pueden no existir
        state_fields = {'recipient_phone', 'amount', 'currency', 'confirmation_pending', 'transaction_id'}
        
        # Separar campos básicos de campos de estado
        # Solo incluir campos básicos que existen
        basic_data = {k: v for k, v in data.items() if k not in state_fields and k in existing_columns}
        # Solo incluir campos de estado que existen
        state_data = {k: v for k, v in data.items() if k in state_fields and k in existing_columns}
        
        # Establecer valores por defecto solo si los campos existen
        if 'currency' in existing_columns and 'currency' not in state_data:
            state_data['currency'] = 'COP'
        if 'confirmation_pending' in existing_columns and 'confirmation_pending' not in state_data:
            state_data['confirmation_pending'] = False
        
        # Combinar solo los campos que existen
        final_data = {**basic_data, **state_data}
        
        # Log para debugging
        logger.debug(
            f"Creando conversación - Campos existentes: {existing_columns}, "
            f"Campos a insertar: {list(final_data.keys())}"
        )

        try:
            # Usar INSERT explícito con SQL raw para solo incluir campos que existen
            # Esto evita que SQLAlchemy intente insertar campos que no existen en la tabla
            table = Conversation.__table__
            
            # Filtrar valores para solo incluir campos que existen en la tabla
            values_to_insert = {
                col_name: final_data[col_name] 
                for col_name in final_data.keys() 
                if col_name in existing_columns
            }
            
            # Construir el INSERT usando SQL raw para tener control total
            if not values_to_insert:
                raise ValueError("No hay campos válidos para insertar")
            
            columns = ', '.join(values_to_insert.keys())
            placeholders = ', '.join([f':{key}' for key in values_to_insert.keys()])
            
            sql = f"""
                INSERT INTO {table.name} ({columns})
                VALUES ({placeholders})
                RETURNING id, created_at
            """
            
            # Ejecutar el INSERT
            result = self.session.execute(sa.text(sql), values_to_insert)
            row = result.fetchone()
            
            # Obtener la entidad creada usando solo campos que existen
            conversation_id = row.id
            
            # Verificar si hay campos de estado que no existen
            state_fields = {'recipient_phone', 'amount', 'currency', 'confirmation_pending', 'transaction_id'}
            missing_state_fields = [field for field in state_fields if field not in existing_columns]
            
            # Si hay campos que no existen, usar SQL raw desde el principio
            if missing_state_fields:
                logger.debug(f"Usando SQL raw para obtener conversación porque faltan campos: {missing_state_fields}")
                # Construir SELECT con solo campos que existen
                basic_columns = ['id', 'user_id', 'started_at', 'ended_at', 'status', 'created_at', 'updated_at', 'deleted_at']
                columns_to_select = [col for col in basic_columns if col in existing_columns]
                columns_str = ', '.join([f'{table.name}.{col}' for col in columns_to_select])
                
                sql_select = f"""
                    SELECT {columns_str}
                    FROM {table.name}
                    WHERE {table.name}.id = :conversation_id
                    LIMIT 1
                """
                
                result = self.session.execute(sa.text(sql_select), {'conversation_id': conversation_id})
                row_data = result.fetchone()
                
                if row_data:
                    # Crear un objeto Conversation manualmente con los datos
                    data_dict = dict(zip(columns_to_select, row_data))
                    db_conversation = Conversation()
                    for key, value in data_dict.items():
                        if hasattr(Conversation, key):
                            setattr(db_conversation, key, value)
                    
                    # No agregar el objeto a la sesión porque merge() intentaría hacer un SELECT
                    # que incluiría campos que no existen. Simplemente retornar el objeto.
                    # El objeto ya existe en la BD, así que no necesitamos agregarlo a la sesión.
                    return db_conversation
                else:
                    return None
            else:
                # Si todos los campos existen, usar el query normal
                try:
                    db_conversation = (
                        self.session.query(Conversation)
                        .filter(Conversation.id == conversation_id)
                        .first()
                    )
                    self.session.flush()
                    return db_conversation
                except ProgrammingError as query_error:
                    # Si el query falla porque hay campos que no existen, usar SQL raw
                    if "column" in str(query_error).lower() or "does not exist" in str(query_error).lower():
                        logger.debug(f"Query falló por campos inexistentes, usando SQL raw: {str(query_error)}")
                        # Hacer rollback del error
                        try:
                            self.session.rollback()
                        except Exception:
                            pass
                        
                        # Construir SELECT con solo campos que existen
                        basic_columns = ['id', 'user_id', 'started_at', 'ended_at', 'status', 'created_at', 'updated_at', 'deleted_at']
                        columns_to_select = [col for col in basic_columns if col in existing_columns]
                        columns_str = ', '.join([f'{table.name}.{col}' for col in columns_to_select])
                        
                        sql_select = f"""
                            SELECT {columns_str}
                            FROM {table.name}
                            WHERE {table.name}.id = :conversation_id
                            LIMIT 1
                        """
                        
                        result = self.session.execute(sa.text(sql_select), {'conversation_id': conversation_id})
                        row_data = result.fetchone()
                        
                        if row_data:
                            # Crear un objeto Conversation manualmente con los datos
                            # Mapear los datos a la entidad
                            data_dict = dict(zip(columns_to_select, row_data))
                            # Crear el objeto solo con los campos que existen
                            # No establecer campos que no existen para evitar errores
                            db_conversation = Conversation()
                            for key, value in data_dict.items():
                                if hasattr(Conversation, key):
                                    setattr(db_conversation, key, value)
                            
                            # No agregar el objeto a la sesión porque merge() intentaría hacer un SELECT
                            # que incluiría campos que no existen. Simplemente retornar el objeto.
                            return db_conversation
                        else:
                            return None
                    else:
                        raise
        except (ProgrammingError, Exception) as e:
            error_str = str(e).lower()
            error_type = type(e).__name__
            
            # Si falla porque los campos no existen, hacer rollback y reintentar
            if "column" in error_str or "does not exist" in error_str or "PendingRollbackError" in error_type:
                logger.warning(
                    f"Algunos campos no existen en la tabla. "
                    f"Por favor ejecuta la migración: alembic upgrade head. "
                    f"Intentando sin campos de estado. Error: {str(e)}"
                )
                # Hacer rollback de la transacción fallida
                try:
                    self.session.rollback()
                except Exception as rollback_error:
                    logger.debug(f"Error en rollback (puede ser normal): {str(rollback_error)}")
                
                # Remover campos de estado y reintentar solo con campos básicos
                # Asegurarse de que basic_data solo tenga campos que existen
                safe_basic_data = {k: v for k, v in basic_data.items() if k in existing_columns}
                
                # Usar INSERT explícito también para el reintento
                table = Conversation.__table__
                # Filtrar valores para solo incluir campos que existen en la tabla
                values_to_insert = {
                    col_name: safe_basic_data[col_name] 
                    for col_name in safe_basic_data.keys() 
                    if col_name in existing_columns
                }
                
                # Construir el INSERT usando SQL raw
                if not values_to_insert:
                    raise ValueError("No hay campos válidos para insertar")
                
                columns = ', '.join(values_to_insert.keys())
                placeholders = ', '.join([f':{key}' for key in values_to_insert.keys()])
                
                sql = f"""
                    INSERT INTO {table.name} ({columns})
                    VALUES ({placeholders})
                    RETURNING id, created_at
                """
                
                result = self.session.execute(sa.text(sql), values_to_insert)
                row = result.fetchone()
                
                conversation_id = row.id
                
                # Verificar si hay campos de estado que no existen
                state_fields = {'recipient_phone', 'amount', 'currency', 'confirmation_pending', 'transaction_id'}
                missing_state_fields = [field for field in state_fields if field not in existing_columns]
                
                # Si hay campos que no existen, usar SQL raw desde el principio
                if missing_state_fields:
                    logger.debug(f"Usando SQL raw para obtener conversación (reintento) porque faltan campos: {missing_state_fields}")
                    # Construir SELECT con solo campos que existen
                    basic_columns = ['id', 'user_id', 'started_at', 'ended_at', 'status', 'created_at', 'updated_at', 'deleted_at']
                    columns_to_select = [col for col in basic_columns if col in existing_columns]
                    columns_str = ', '.join([f'{table.name}.{col}' for col in columns_to_select])
                    
                    sql_select = f"""
                        SELECT {columns_str}
                        FROM {table.name}
                        WHERE {table.name}.id = :conversation_id
                        LIMIT 1
                    """
                    
                    result = self.session.execute(sa.text(sql_select), {'conversation_id': conversation_id})
                    row_data = result.fetchone()
                    
                    if row_data:
                        # Crear un objeto Conversation manualmente con los datos
                        data_dict = dict(zip(columns_to_select, row_data))
                        db_conversation = Conversation()
                        for key, value in data_dict.items():
                            if hasattr(Conversation, key):
                                setattr(db_conversation, key, value)
                        
                        # No agregar el objeto a la sesión porque merge() intentaría hacer un SELECT
                        # que incluiría campos que no existen. Simplemente retornar el objeto.
                        return db_conversation
                    else:
                        return None
                else:
                    # Si todos los campos existen, usar el query normal
                    try:
                        db_conversation = (
                            self.session.query(Conversation)
                            .filter(Conversation.id == conversation_id)
                            .first()
                        )
                        self.session.flush()
                        return db_conversation
                    except ProgrammingError as query_error:
                        # Si el query falla porque hay campos que no existen, usar SQL raw
                        if "column" in str(query_error).lower() or "does not exist" in str(query_error).lower():
                            logger.debug(f"Query falló por campos inexistentes, usando SQL raw: {str(query_error)}")
                            # Hacer rollback del error
                            try:
                                self.session.rollback()
                            except Exception:
                                pass
                            
                            # Construir SELECT con solo campos que existen
                            basic_columns = ['id', 'user_id', 'started_at', 'ended_at', 'status', 'created_at', 'updated_at', 'deleted_at']
                            columns_to_select = [col for col in basic_columns if col in existing_columns]
                            columns_str = ', '.join([f'{table.name}.{col}' for col in columns_to_select])
                            
                            sql_select = f"""
                                SELECT {columns_str}
                                FROM {table.name}
                                WHERE {table.name}.id = :conversation_id
                                LIMIT 1
                            """
                            
                            result = self.session.execute(sa.text(sql_select), {'conversation_id': conversation_id})
                            row_data = result.fetchone()
                            
                            if row_data:
                                # Crear un objeto Conversation manualmente con los datos
                                data_dict = dict(zip(columns_to_select, row_data))
                                # Crear el objeto solo con los campos que existen
                                db_conversation = Conversation()
                                for key, value in data_dict.items():
                                    if hasattr(Conversation, key):
                                        setattr(db_conversation, key, value)
                                
                                # No agregar el objeto a la sesión porque merge() intentaría hacer un SELECT
                                # que incluiría campos que no existen. Simplemente retornar el objeto.
                                return db_conversation
                            else:
                                return None
                        else:
                            raise
            
            # Para otros errores, hacer rollback si es necesario
            if "PendingRollbackError" not in error_type:
                try:
                    self.session.rollback()
                except Exception:
                    pass
            raise

    def update(
        self, conversation_id: int, conversation_data: ConversationUpdate
    ) -> Conversation | None:
        db_conversation = self.get_by_id(conversation_id)
        if not db_conversation:
            return None

        # Convertir el enum a su valor antes de actualizar
        update_data = conversation_data.model_dump(exclude_unset=True, mode="python")
        if "status" in update_data:
            if isinstance(update_data["status"], ConversationStatus):
                update_data["status"] = update_data["status"].value
            elif isinstance(update_data["status"], str):
                update_data["status"] = update_data["status"].lower()
        
        # Filtrar campos que no existen en la tabla
        existing_columns = self._get_existing_columns()
        # Campos de estado que pueden no existir
        state_fields = {'recipient_phone', 'amount', 'currency', 'confirmation_pending', 'transaction_id'}
        
        # Separar campos básicos de campos de estado
        basic_update = {k: v for k, v in update_data.items() if k not in state_fields}
        state_update = {k: v for k, v in update_data.items() if k in state_fields and k in existing_columns}
        
        # Combinar solo los campos que existen
        filtered_update = {**basic_update, **state_update}
        
        try:
            return super().update(db_conversation, filtered_update)
        except ProgrammingError as e:
            # Si falla porque los campos no existen, hacer rollback y reintentar
            if "column" in str(e).lower() or "does not exist" in str(e).lower():
                logger.warning(
                    f"Algunos campos no existen en la tabla. "
                    f"Por favor ejecuta la migración: alembic upgrade head. "
                    f"Intentando sin campos de estado. Error: {str(e)}"
                )
                # Hacer rollback de la transacción fallida
                self.session.rollback()
                # Remover campos de estado y reintentar solo con campos básicos
                return super().update(db_conversation, basic_update)
            raise
        except Exception as e:
            # Para cualquier otro error, hacer rollback
            if "rollback" not in str(e).lower():
                self.session.rollback()
            raise

    def delete(self, conversation_id: int) -> bool:
        """
        Elimina una conversación (soft delete).
        El listener de SQLAlchemy interceptará el DELETE y establecerá deleted_at automáticamente.
        """
        db_conversation = self.get_by_id(conversation_id)
        if not db_conversation:
            return False

        # El listener de SQLAlchemy manejará el soft delete automáticamente
        # Solo necesitamos llamar a session.delete y el listener convertirá en UPDATE
        super().delete(db_conversation)
        return True

-- Función de PostgreSQL para manejar soft delete automáticamente
-- Esta función crea una vista que filtra automáticamente los registros con deleted_at IS NOT NULL

-- Función helper para verificar si una tabla tiene deleted_at
CREATE OR REPLACE FUNCTION has_deleted_at_column(table_name text)
RETURNS boolean AS $$
BEGIN
    RETURN EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = has_deleted_at_column.table_name
        AND column_name = 'deleted_at'
    );
END;
$$ LANGUAGE plpgsql;

-- Función para crear una política de soft delete en una tabla
-- Esta función se puede llamar para cualquier tabla que tenga deleted_at
CREATE OR REPLACE FUNCTION setup_soft_delete_policy(table_name text)
RETURNS void AS $$
DECLARE
    view_name text;
BEGIN
    view_name := table_name || '_active';
    
    -- Crear vista que filtra automáticamente los registros eliminados
    EXECUTE format('
        CREATE OR REPLACE VIEW %I AS
        SELECT * FROM %I
        WHERE deleted_at IS NULL;
    ', view_name, table_name);
    
    -- Crear trigger para actualizar deleted_at en lugar de DELETE
    EXECUTE format('
        CREATE OR REPLACE FUNCTION %I_soft_delete()
        RETURNS TRIGGER AS $trigger$
        BEGIN
            UPDATE %I SET deleted_at = NOW() WHERE id = OLD.id;
            RETURN NULL;
        END;
        $trigger$ LANGUAGE plpgsql;
    ', table_name, table_name);
    
    -- Asignar el trigger a la tabla (esto se hace manualmente o en migraciones específicas)
    -- DROP TRIGGER IF EXISTS soft_delete_trigger ON table_name;
    -- CREATE TRIGGER soft_delete_trigger
    --     INSTEAD OF DELETE ON table_name
    --     FOR EACH ROW EXECUTE FUNCTION table_name_soft_delete();
END;
$$ LANGUAGE plpgsql;

-- Función para aplicar soft delete a la tabla transactions
CREATE OR REPLACE FUNCTION apply_soft_delete_to_transactions()
RETURNS void AS $$
BEGIN
    -- Crear vista activa
    CREATE OR REPLACE VIEW transactions_active AS
    SELECT * FROM transactions
    WHERE deleted_at IS NULL;
    
    -- Crear función de soft delete
    CREATE OR REPLACE FUNCTION transactions_soft_delete()
    RETURNS TRIGGER AS $trigger$
    BEGIN
        UPDATE transactions 
        SET deleted_at = NOW() 
        WHERE id = OLD.id;
        RETURN NULL;
    END;
    $trigger$ LANGUAGE plpgsql;
    
    -- Nota: Los triggers INSTEAD OF solo funcionan en vistas
    -- Para tablas, usamos BEFORE DELETE trigger
    DROP TRIGGER IF EXISTS soft_delete_transactions_trigger ON transactions;
    CREATE TRIGGER soft_delete_transactions_trigger
        BEFORE DELETE ON transactions
        FOR EACH ROW
        EXECUTE FUNCTION transactions_soft_delete();
END;
$$ LANGUAGE plpgsql;




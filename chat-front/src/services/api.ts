import axios, { AxiosInstance, AxiosError } from 'axios';

const API_BASE_URL = 'http://localhost:3300/api/v1';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  username: string;
}

export interface ChatMessageRequest {
  message: string;
  conversation_id?: number | null;
}

export interface ChatResponse {
  conversation_id: number;
  response: string;
  status: string;
}

class ApiService {
  private axiosInstance: AxiosInstance;

  constructor() {
    this.axiosInstance = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Interceptor para agregar el token de autenticación
    this.axiosInstance.interceptors.request.use(
      (config) => {
        const token = localStorage.getItem('auth_token');
        if (token) {
          config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
      },
      (error) => {
        return Promise.reject(error);
      }
    );

    // Interceptor para manejar errores
    this.axiosInstance.interceptors.response.use(
      (response) => response,
      (error: AxiosError) => {
        if (error.response) {
          const errorData = error.response.data as { detail?: string };
          throw new Error(errorData.detail || error.message || 'Error desconocido');
        } else if (error.request) {
          throw new Error('No se pudo conectar con el servidor');
        } else {
          throw new Error(error.message || 'Error desconocido');
        }
      }
    );
  }

  async login(credentials: LoginRequest): Promise<LoginResponse> {
    const response = await this.axiosInstance.post<LoginResponse>('/auth/login', credentials);
    return response.data;
  }

  async sendChatMessage(message: ChatMessageRequest): Promise<ChatResponse> {
    const response = await this.axiosInstance.post<ChatResponse>('/conversations/chat', message);
    return response.data;
  }
}

export const apiService = new ApiService();


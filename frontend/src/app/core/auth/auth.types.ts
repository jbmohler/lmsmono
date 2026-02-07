/**
 * Authentication type definitions.
 */

export interface User {
  id: string;
  username: string;
  fullName: string | null;
  capabilities: string[];
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  id: string;
  username: string;
  full_name: string | null;
  capabilities: string[];
}

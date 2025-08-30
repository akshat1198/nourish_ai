// This is a template file showing how to define TypeScript types and interfaces
// for your frontend application.

// Example 1: Basic Interface
// Use interfaces to define the shape of objects in your application
export interface User {
  id: number;
  name: string;
  email?: string; // Optional property (note the ?)
}

// Example 2: Generic Type
// Create reusable types that can work with different data types
export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

// Example 3: Union Types
// Define a type that can be one of several types
export type Status = 'idle' | 'loading' | 'success' | 'error';

// Example 4: Extending Interfaces
// Interfaces can extend other interfaces
export interface BaseModel {
  id: number;
  createdAt: Date;
  updatedAt: Date;
}

export interface ExtendedModel extends BaseModel {
  additionalField: string;
}

// Example 5: Type Aliases
// Use type aliases to create custom types
export type Dictionary<T> = {
  [key: string]: T;
};

// Example 6: Enum
// Use enums for predefined sets of values
export enum Theme {
  Light = 'light',
  Dark = 'dark',
  System = 'system'
}

// You can delete or modify these examples and add your own types
// based on your application's needs.

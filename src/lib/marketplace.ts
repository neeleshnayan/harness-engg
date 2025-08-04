import api from './api';

export interface MarketplaceItem {
  id: string;
  category: string;
  name: string;
  description: string;
  price: number;
  linkedin?: string;
  youtube?: string;
  x?: string;
  token_name?: string;
  is_minting_active?: boolean;
  owner_id?: string;
  created_at?: string;
  updated_at?: string;
}

export interface MarketplaceCategories {
  id: string;
  categories: string[];
}

export class MarketplaceService {
  static async getCategories(): Promise<MarketplaceCategories> {
    try {
      const response = await api.get('/api/v1/marketplace/categories');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch categories:', error);
      throw error;
    }
  }

  static async getMarketplaceItems(): Promise<MarketplaceItem[]> {
    try {
      const response = await api.get('/api/v1/marketplace');
      return response.data;
    } catch (error) {
      console.error('Failed to fetch marketplace items:', error);
      throw error;
    }
  }

  static async getMarketplaceItemsByCategory(category: string): Promise<MarketplaceItem[]> {
    try {
      const response = await api.get(`/api/v1/marketplace/category/${encodeURIComponent(category)}`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch marketplace items by category:', error);
      throw error;
    }
  }

  static async getMarketplaceItem(itemId: string): Promise<MarketplaceItem> {
    try {
      const response = await api.get(`/api/v1/marketplace/item/${itemId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch marketplace item:', error);
      throw error;
    }
  }

  static async getBusinessItemsByOwner(ownerId: string): Promise<MarketplaceItem[]> {
    try {
      const response = await api.get(`/api/v1/marketplace/business/${ownerId}`);
      return response.data;
    } catch (error) {
      console.error('Failed to fetch business items:', error);
      throw error;
    }
  }
} 
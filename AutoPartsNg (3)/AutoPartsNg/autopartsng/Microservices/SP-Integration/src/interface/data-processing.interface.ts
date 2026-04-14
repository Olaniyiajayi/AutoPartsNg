export interface IStockItem {
  lineItem: {
    stockNum: string;
    totalAvailable: string;
  };
}

export interface IProcessedStockItem {
  sku: string;
  quantity: string;
}
export interface IItemToUpdate {
  sku: string;
  quantity: string;
  createdAt?: string;
}

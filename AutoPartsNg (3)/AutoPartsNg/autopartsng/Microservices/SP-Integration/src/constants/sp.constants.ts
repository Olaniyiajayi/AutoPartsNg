export const FEED_STATUS = {
  IN_QUEUE: 'IN_QUEUE',
  DONE: 'DONE',
  CANCELLED: 'CANCELLED',
  FATAL: 'FATAL',
};

export const SP_API_URL = {
  LWA_TOKEN_URL: 'https://api.amazon.com/auth/o2/token',
  CREATE_DESTINATION: 'https://sellingpartnerapi-na.amazon.com/notifications/v1/destinations',
  CREATE_SUBSCRIPTION: 'https://sellingpartnerapi-na.amazon.com/notifications/v1/subscriptions',
  ITEM_LISTING: `https://sellingpartnerapi-na.amazon.com/listings/2021-08-01/items/A175CPO7VUAYDU`,
  ORDER_LISTING: `https://sellingpartnerapi-na.amazon.com/orders/v0/orders`,
};

export const NOTIFICATION_DESTINATION = {
  NAME: 'FeedProcessingQueueDestination',
};

export const LWA_GRANT_TYPES = {
  REFRESH_TOKEN: 'refresh_token',
  CLIENT_CREDENTIALS: 'client_credentials',
};

export const ORDER_STATUS = {
  PENDING: 'Pending',
  DONE: 'Done',
};

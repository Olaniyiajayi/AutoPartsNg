export const DDI_USERNAME = process.env.DDI_USERNAME || '';
export const DDI_PASSWORD = process.env.DDI_PASSWORD || '';
export const DDI_PASSPHRASE = process.env.DDI_PASSPHRASE || '';
export const DDI_CONTACTNAME = process.env.DDI_CONTACTNAME || '';
export const MANAGE_INVENTORY_TABLE = process.env.MANAGE_INVENTORY_TABLE || '';
export const MANAGE_SKU_TABLE = process.env.MANAGE_SKU_TABLE || '';
export const MANAGE_ORDER_TABLE = process.env.MANAGE_ORDER_TABLE || '';
export const MANAGE_ORDER_ITEM_TABLE = process.env.MANAGE_ORDER_ITEM_TABLE || '';
export const PROCESSED_DATA_SQS_URL = process.env.PROCESSED_DATA_SQS_URL || '';
export const CREATE_ORDER_SQS_URL = process.env.CREATE_ORDER_SQS_URL || '';
export const SP_REGION = process.env.SP_REGION || '';
export const SP_REFRESH_TOKEN =
  process.env.SP_REFRESH_TOKEN ||
  'Atzr|IwEBIHOymubOAEOCrCjsmY87vp48jYoYrrKbRGZl_zZ6gr8TtTRxXLlCeNbDO4hI2flfrYHQWXRWnL-po1G5wPf1cOHUbtcNWLet1USgtKym1LNy68_WVz0uo-y8tk8bBy0L03CDBsyg_u1E5q7t9Le6S41AkQhnwSnlqXsuULWIKIYehH1d7gUIHvhqaRBpSuvN3TBTY_-81oJ6jQRxKeQv56Q4f4bp_T6MJa6WPssf0Quwp_d6sdEp7mYw3eflLi-t6UcA5eKbM9DUqf9SwWg4Tc89n2_Icz0anYJabuFIqS-9kuR_sIlavM5RDw9QEpYN1Y0';
export const SP_APP_CLIENT_ID =
  process.env.SP_APP_CLIENT_ID || 'amzn1.application-oa2-client.249e6cce6f224481b875b581d0bdbf5f';
export const SP_APP_CLIENT_SECRET =
  process.env.SP_APP_CLIENT_SECRET ||
  'amzn1.oa2-cs.v1.3967fc137ddd0a0ed77ca54155bc36bf3448837f16ee642374dc62b084a2f7d1';
export const SP_SELLER_ID = process.env.SP_SELLER_ID || 'A175CPO7VUAYDU';
export const SP_MARKETPLACE_ID = process.env.SP_MARKETPLACE_ID || 'ATVPDKIKX0DER';
export const FEED_PROCESSING_SQS_ARN =
  process.env.FEED_PROCESSING_SQS_ARN || 'arn:aws:sqs:us-east-1:693920098032:prod-feed-processing-queue';

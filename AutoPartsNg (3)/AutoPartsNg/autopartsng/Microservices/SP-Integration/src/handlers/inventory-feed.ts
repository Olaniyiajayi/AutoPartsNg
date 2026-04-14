import {
  addFeedIdInDB,
  createFeed,
  generateFeedDocument,
  generateFeedJSON,
  getFeed,
  uploadFeed,
} from '../service/inventory-feed.service';
import { errorResponse, successResponse } from '../helpers/response.helper';
import { ERROR_MESSAGE, SUCCESS_MESSAGE } from '../constants/messages.contants';

export const lambdaHandler = async (event: { Records: any }) => {
  console.log('🚀 ~ lambdaHandler ~ event:::::::', JSON.stringify(event));
  try {
    for (const record of event.Records) {
      const data = JSON.parse(record.body);
      console.log('Processing data::::::::', data);
      console.log('data.length::::::::::', data.length);

      // Implement your logic to feed data to Amazon services
      if (data.length) {
        // Generate the JSON feed
        const feedContent = generateFeedJSON(data);
        console.log('🚀 ~ lambdaHandler ~ feedContent::::::', feedContent);

        // Generate feed document
        const feedDocument: any = await generateFeedDocument();
        console.log('🚀 ~ lambdaHandler ~ feedDocument::::::::::::', feedDocument);

        // Upload JSON feed pass as string
        await uploadFeed(feedDocument, JSON.stringify(feedContent));

        // Create Feed to update inventory quantity on amazon
        const feedResponse = await createFeed(feedDocument);
        console.log('🚀 ~ lambdaHandler ~ feedResponse:::::::', feedResponse);

        // Get the feed info to know the processing status
        const feedInfo: any = await getFeed(feedResponse.feedId);
        console.log('🚀 ~ lambdaHandler ~ feedInfo::::::', feedInfo);

        // Add feedId into dynamodb database for each sku
        await addFeedIdInDB(data, feedInfo);
      }
    }

    return successResponse(null, SUCCESS_MESSAGE.FEED_SUBMISSION_SUCCESS);
  } catch (err: any) {
    console.log(err);
    return errorResponse(null, err.message || ERROR_MESSAGE.INTERNAL_SERVER_ERROR);
  }
};

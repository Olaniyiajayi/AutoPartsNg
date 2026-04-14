import { ERROR_MESSAGE, SUCCESS_MESSAGE } from '../constants/messages.contants';
import { errorResponse, successResponse } from '../helpers/response.helper';
import { getFeed } from '../service/inventory-feed.service';
import { getInQueueItems, updateFeedStatus } from '../service/update-feed-status.service';

export const lambdaHandler = async () => {
  try {
    const inQueueFeedItems = await getInQueueItems();
    console.log('🚀 ~ lambdaHandler ~ inQueueFeedItems::::', inQueueFeedItems, inQueueFeedItems.length);

    if (inQueueFeedItems.length) {
      // Get unique feedIds
      const uniqueFeedIds = [...new Set(inQueueFeedItems.map((item) => item.feedId.S))];
      console.log('🚀 ~ lambdaHandler ~ uniqueFeedIds::::::', uniqueFeedIds);

      if (!uniqueFeedIds.length) return;

      for (const feedId of uniqueFeedIds) {
        // Get the feed info to know the processing status
        const feedInfo: any = await getFeed(feedId!);
        console.log('🚀 ~ lambdaHandler ~ feedInfo::::::', feedInfo);

        if (!feedInfo.processingStatus) return;

        // Find all items with this feedId and update their status
        const itemsToUpdate = inQueueFeedItems.filter((item) => item.feedId.S === feedId);
        console.log('🚀 ~ lambdaHandler ~ itemsToUpdate:::::', itemsToUpdate.length);

        for (const item of itemsToUpdate) {
          if (item?.sku?.S) {
            await updateFeedStatus(item?.sku?.S, feedInfo.processingStatus);
          }
        }
      }
    }
    return successResponse(null, SUCCESS_MESSAGE.FEED_UPDATION_SUCCESS);
  } catch (err: any) {
    console.log(err);
    return errorResponse(null, err.message || ERROR_MESSAGE.INTERNAL_SERVER_ERROR);
  }
};

Built a YouTube video recommendation system based on sentiment of video comments.
The sentiment analysis is done using MonkeyLearn.
Results are placed into a MongoDB database.
Sentiment scores are adjusted for number of comments with scores adjusted downward with fewer comments.
This adjustment is done using a customized sigmoid function.
A neural network is used to predict up and downvotes of the video based on sentiment score and other features.

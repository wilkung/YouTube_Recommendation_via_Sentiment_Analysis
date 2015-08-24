# d3, flask
# doesn't seem to be getting videos on first page - 


import bs4
import urllib2
import requests
import json
import math
import pprint
import pymongo
import numpy as np
import neurolab as nl
    
    
def custom_sigmoid(x):
    return 2.0 / (1 + math.e**(-0.08 * x)) - 1


conn = pymongo.MongoClient()
db = conn.db_query
YT_sentsNN = db.YT_sentsNN
    
# What do we want to query from youtube?
query = "hawaii".replace(" ", "+")
final_results = { }

if YT_sentsNN.find({ '_id' : query }).count() == 0:

    # Retrieve the HTML search results
    search_url = "https://www.youtube.com/results?search_sort=video_view_count&search_query=%s" % query
    data = urllib2.urlopen(search_url)
    soup = bs4.BeautifulSoup(data)
    titles = soup.findAll('h3', attrs={'class': 'yt-lockup-title '})
    
    # Get all video IDs for these results from youtube
    video_ids = []
    for title in titles:
        link = title.findAll('a')
        if link:
            video_ids.append(link[0].attrs['href'].split("=")[-1])
    
    # This will store video_id => final score
    final_results = {}
    
    # For every video result
    for video_id in video_ids:
        print("Retrieving html for video %s" % video_id)
        
        url = r'https://www.youtube.com/watch?v=%s' % video_id
        data = urllib2.urlopen(url) 
        
        # Pull out featurea of video from html
        soup = bs4.BeautifulSoup(data)
        view_count = int(soup.findAll(attrs={'class': 'watch-view-count'})[0].text.replace(',', ''))   
    
        ratings_elem = soup.find_all(attrs={'id': 'watch8-sentiment-actions'})[0]
        ratings = ratings_elem.select('button.yt-uix-button span')
        up_votes = int(ratings[0].text.replace(',', ''))
        down_votes = int(ratings[2].text.replace(',', ''))
        
        subscribers = int(soup.find_all(attrs={'class': 'yt-subscription-button-subscriber-count-branded-horizontal'})[0].text.replace(',', ''))        
        
        # Grab the page source for video comment page
        url = r'http://www.youtube.com/all_comments?v=%s' % video_id
        data = urllib2.urlopen(url) #example XhFtHW4YB7M
        
        # Pull out comments from html
        soup = bs4.BeautifulSoup(data)
        cmnts = soup.findAll(attrs={'class': 'comment-text-content'})
        
        print("Getting video comments")
    
        # Create list of only comment text
        comments_text = [cmnt.text for cmnt in cmnts if cmnt.text]
        
        print("Sending over to MonkeyLearn")
        
        if comments_text:
            # Create a request to MonkeyLearn sentiment API
            response = requests.post(
                "https://api.monkeylearn.com/v2/classifiers/cl_qkjxv9Ly/classify/?",
                data = json.dumps({'text_list': comments_text}),
                headers={'Authorization': 'Token 9112d82b0565d664965ecb5ab2b3b1c1ac98aa4f',
                        'Content-Type': 'application/json'})
            
            # Grab their results in json        
            results = json.loads(response.text)# convert json response to python
        
            print("Results found, calculating score")
            
            # What are the sentiment results?
            idx = 0
            neutral_count = 0.0
            positive_count = 0.0
            negative_count = 0.0
            for idx in range(len(results['result'])):
                label = results['result'][idx][0]['label']
                if label == 'neutral': neutral_count+=1
                elif label == 'positive': positive_count+=1
                elif label == 'negative': negative_count+=1
                #print comments_text[idx], '-----', label
            
            # Get final score for this video    
            # Formula = ((pos-neg)/total) * f(total)
            total = positive_count + negative_count
            if total != 0:        
                score = ((positive_count - negative_count) / total) * custom_sigmoid(total)
            else:
                score = 0.0
        else:
            score = 0.0        
        
        # Store results in dict
        final_results[video_id] = {
            'sentiment_score': score,
            'subscribers': subscribers,
            'view_count': view_count,
            'output': (up_votes - down_votes) / float(up_votes + down_votes)
        }
        print("Done")

    #save data to mongo
    final_results["_id"] = query
    YT_sentsNN.insert_one(final_results)

else:
    final_results = YT_sentsNN.find_one({ '_id' : query })


import operator
sorted_final_results = sorted(final_results.items(), reverse=True,key=operator.itemgetter(1))

# Print results
pprint.pprint(sorted_final_results)



# PREDICT UPVOTES - DOWNVOTES BY USING SUBSCRIBERS, MY SENTIMENT SCORE AND VIEW COUNT

#Factors to use to predict upvotes-downvotes    
sentiment_score_query = [ sorted_final_results[i][1]['sentiment_score'] for i in range(1,21) ]
subscribers_query = [ sorted_final_results[i][1]['subscribers'] for i in range(1,21) ]
view_count_query = [ sorted_final_results[i][1]['view_count'] for i in range(1,21) ]

#upvotes-downvotes: Predict this
output_query = [ sorted_final_results[i][1]['output'] for i in range(1,21) ]

NNinput = np.column_stack([sentiment_score_query, subscribers_query, view_count_query])
NNtarget = a = np.array( output_query )
NNtarget = NNtarget.reshape(-1,1)

ssrange = [ -1, 1 ]
#subrange = [ min(subscribers_query), max(subscribers_query) ]
subrange = [ 0, 10000000 ]
#viewrange = [ min(view_count_query), max(view_count_query) ]
viewrange = [ 0, 100000000 ]

# Create network with 2 inputs, 5 neurons in input layer and 1 in output layer
net = nl.net.newff( [ ssrange, subrange, viewrange ], [5, 1] )
err = net.train(NNinput, NNtarget, epochs=500, show=100, goal=0.02)

# do in-sample prediction
out = net.sim(NNinput)
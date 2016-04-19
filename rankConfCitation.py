from google_scholar import * 
import sys

def queryCitation(paperList):

	querier = ScholarQuerier()
	query = SearchScholarQuery()
	query.set_scope(True)

	citationDict = {}

	for paper in paperList:	
		query.set_words(paper)
		querier.send_query(query)

		articles = querier.articles
		
		print paper, len(articles)

		if len(articles) != 1:
			
			nameCitation = {}

			for art in articles:
				if art.attrs['title'][0] in nameCitation:
					if int(articles[0].attrs['num_citations'][0]) > nameCitation[art.attrs['title'][0]]:
						nameCitation[art.attrs['title'][0]] = int(articles[0].attrs['num_citations'][0])
				else:
					nameCitation[art.attrs['title'][0]] = int(articles[0].attrs['num_citations'][0])

				
			for key in nameCitation:
				print key, nameCitation[key]

		else:
			citationDict[paper] = int(articles[0].attrs['num_citations'][0])

	return citationDict

if __name__=='__main__':
	sPaperFile = sys.argv[1]


	with open(sPaperFile) as f:
		paperList = f.read().splitlines()

	citationDict = queryCitation(paperList)

	print len(citationDict)

	#for key in citationDict:
	#	print key, citationDict[key]

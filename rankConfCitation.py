
import sys
import getopt

def usage():
	print '-f', '--file', 'file containing paper list'
	print '-d', '--database', 'database to query'
	print '-y', '--year', 'when papers are published'


try:
	opts, args = getopt.getopt(sys.argv[1:], 'd:y:f:c:', ['database==', 'year==', 'file==', 'conference=='])
except getopt.GetoptError:
	usage()
	sys.exit(2)



sFile = None
sYear = None
sDB = None
sConf = None

for opt, arg in opts:
	if opt in ('-f', '--file'):
		sFile = arg
	elif opt in ('-y', '--year'):
		sYear = arg
	elif opt in ('-d', '--database'):
		sDB = arg
	elif opt in ('-c', '--conference'):
		sConf = arg


if cmp(sDB, 'google') == 0:
	from google_scholar import * 
elif cmp(sDB, 'acm') == 0:
	from acmld import *
else:
	usage()
	sys.exit(2)




def queryGoogleCitation(paperList):

	querier = ScholarQuerier()
	query = SearchScholarQuery()
	query.set_scope(True)

	citationDict = {}

	for paper in paperList:	
		query.set_words(paper)
		querier.send_query(query)

		articles = querier.articles

		if len(articles) != 1:			
			nameCitation = {}
			for art in articles:
				if art.attrs['title'][0] in nameCitation:
					if int(articles[0].attrs['num_citations'][0]) > nameCitation[art.attrs['title'][0]]:
						nameCitation[art.attrs['title'][0]] = int(articles[0].attrs['num_citations'][0])
				else:
					nameCitation[art.attrs['title'][0]] = int(articles[0].attrs['num_citations'][0])

			maxLength = 10000

			for key in nameCitation:
				if len(key) < maxLength:
					maxLength = len(key)
					paper = key

			citationDict[paper] = nameCitation[paper]

		else:
			citationDict[paper] = int(articles[0].attrs['num_citations'][0])

	return citationDict


def filterByYear(articles, sYear):
	artList = []

	for art in articles:
		if art.attrs['date'][0] != None and art.attrs['date'][0].find(sYear) != -1:
			artList.append(art)

	return artList

def filterByConference(articles, sConf):
	artList = []

	for art in articles:
		if art.attrs['conference'][0] != None and art.attrs['conference'][0].find(sConf) != -1:
			artList.append(art)

	return artList

def filterByTitle(articles, sTitle):
	artList = []

	sTitle.replace(':', '')
	wordList = sTitle.split()

	for art in articles:
		flag = True

		for word in wordList:
			if art.attrs['title'][0] != None and art.attrs['title'][0].find(word) == -1:
				flag = False
				break

		if flag:
			artList.append(art)

	return artList



def queryACMCitation(paperList):
	querier = ScholarQuerier()
	query = SearchScholarQuery()

	
	citationDict = {}
	articleDict = {}

	for paper in paperList:
		query.set_title(paper)
		querier.send_query(query)

		articles = querier.articles

		if len(articles) != 1:
			articles = filterByYear(articles, sYear)			
			articles = filterByConference(articles, sConf)
			articles = filterByTitle(articles, paper)

			if len(articles) != 1:
				print paper, len(articles)
			else:
				citationDict[paper] = int(articles[0].attrs['num_citations'][0])
				articleDict[paper] = articles[0]

		else:
			citationDict[paper] = int(articles[0].attrs['num_citations'][0])
			articleDict[paper] = articles[0]

	#txt(querier)

	return citationDict, articleDict

if __name__=='__main__':
	sPaperFile = sFile

	with open(sPaperFile) as f:
		paperList = f.read().splitlines()


	if cmp(sDB, 'google') == 0:
		citationDict = queryGoogleCitation(paperList)
	elif cmp(sDB, 'acm') == 0:
		citationDict, articleDict = queryACMCitation(paperList)


	print 
	print

	for w in sorted(citationDict, key=citationDict.get, reverse=True):
		print w, citationDict[w]
		print(encode(articleDict[w].as_txt()) + '\n')



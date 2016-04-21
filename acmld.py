import optparse
import os
import sys
import re
import getopt

try:
	# Try importing for Python 3
	# pylint: disable-msg=F0401
	# pylint: disable-msg=E0611
	from urllib.request import HTTPCookieProcessor, Request, build_opener
	from urllib.parse import quote, unquote
	from http.cookiejar import MozillaCookieJar
except ImportError:
	# Fallback for Python 2
	from urllib2 import Request, build_opener, HTTPCookieProcessor
	from urllib import quote, unquote
	from cookielib import MozillaCookieJar


# Import BeautifulSoup -- try 4 first, fall back to older
try:
	from bs4 import BeautifulSoup
except ImportError:
	try:
		from BeautifulSoup import BeautifulSoup
	except ImportError:
		print('We need BeautifulSoup, sorry...')
		sys.exit(1)

# Support unicode in both Python 2 and 3. In Python 3, unicode is str.
if sys.version_info[0] == 3:
	unicode = str # pylint: disable-msg=W0622
	encode = lambda s: unicode(s) # pylint: disable-msg=C0103
else:
	def encode(s):
		if isinstance(s, basestring):
			return s.encode('utf-8') # pylint: disable-msg=C0103
		else:
			return str(s)

class Error(Exception):
	"""Base class for any Scholar error."""


class FormatError(Error):
	"""A query argument or setting was formatted incorrectly."""


class QueryArgumentError(Error):
	"""A query did not have a suitable set of arguments."""


class ScholarConf(object):
	"""Helper class for global settings."""

	VERSION = '0.10'
	LOG_LEVEL = 1
	MAX_PAGE_RESULTS = 20 # Current maximum for per-page results
	SCHOLAR_SITE = 'http://dl.acm.org/'

	# USER_AGENT = 'Mozilla/5.0 (X11; U; FreeBSD i386; en-US; rv:1.9.2.9) Gecko/20100913 Firefox/3.6.9'
	# Let's update at this point (3/14):
	USER_AGENT = 'Mozilla/5.0 (X11; Linux x86_64; rv:27.0) Gecko/20100101 Firefox/27.0'

	# If set, we will use this file to read/save cookies to enable
	# cookie use across sessions.
	COOKIE_JAR_FILE = None

class ScholarUtils(object):
	"""A wrapper for various utensils that come in handy."""

	LOG_LEVELS = {'error': 1,
					'warn':  2,
					'info':  3,
					'debug': 4}

	@staticmethod
	def ensure_int(arg, msg=None):
		try:
			return int(arg)
		except ValueError:
			raise FormatError(msg)

	@staticmethod
	def log(level, msg):
		if level not in ScholarUtils.LOG_LEVELS.keys():
			return
		if ScholarUtils.LOG_LEVELS[level] > ScholarConf.LOG_LEVEL:
			return
		sys.stderr.write('[%5s]  %s' % (level.upper(), msg + '\n'))
		sys.stderr.flush()

class ScholarArticle(object):
	"""
	A class representing articles listed on Google Scholar.  The class
	provides basic dictionary-like behavior.
	"""
	def __init__(self):
		# The triplets for each keyword correspond to (1) the actual
		# value, (2) a user-suitable label for the item, and (3) an
		# ordering index:
		self.attrs = {
			'title':         [None, 'Title',          0],
			'url':           [None, 'URL',            1],
			'date':          [None, 'Date',           2],
			'conference':	 [None, 'Conerence',	  3],	
			'num_citations': [0,    'Citations',      4],

        }

		# The citation data in one of the standard export formats,
		# e.g. BibTeX.
		self.citation_data = None

	def __getitem__(self, key):
		if key in self.attrs:
			return self.attrs[key][0]
		return None

	def __len__(self):
		return len(self.attrs)

	def __setitem__(self, key, item):
		if key in self.attrs:
			self.attrs[key][0] = item
		else:
			self.attrs[key] = [item, key, len(self.attrs)]

	def __delitem__(self, key):
		if key in self.attrs:
			del self.attrs[key]

	def set_citation_data(self, citation_data):
		self.citation_data = citation_data

	def as_txt(self):
		# Get items sorted in specified order:
		items = sorted(list(self.attrs.values()), key=lambda item: item[2])
		# Find largest label length:
		max_label_len = max([len(str(item[1])) for item in items])
		fmt = '%%%ds %%s' % max_label_len
		res = []
		for item in items:
			if item[0] is not None:
				res.append(fmt % (item[1], item[0]))
		return '\n'.join(res)


class ScholarArticleParser(object):
	"""
	ScholarArticleParser can parse HTML document strings obtained from
	ACM Digital Library. 
	"""
	def __init__(self, site=None):
		self.soup = None
		self.article = None
		self.site = site or ScholarConf.SCHOLAR_SITE
		self.year_re = re.compile(r'\b(?:20|19)\d{2}\b')
		self.citation = re.compile(r'Citation Count:[\s]+([0-9]+)')

	def handle_article(self, art):
		"""
		The parser invokes this callback on each article parsed
		successfully.  In this base class, the callback does nothing.
		"""	

	def _clean_article(self):
		"""
		This gets invoked after we have parsed an article, to do any
		needed cleanup/polishing before we hand off the resulting
		article.
		"""
		if self.article['title']:
			self.article['title'] = self.article['title'].strip()

	def parse(self, html):
		"""
		This method initiates parsing of HTML content, cleans resulting
		content as needed, and notifies the parser instance of
		resulting instances via the handle_article callback.
		"""
		self.soup = BeautifulSoup(html)


		# Now parse out listed articles:
		for div in self.soup.findAll(ScholarArticleParser._tag_contain_article):	
			self._parse_article(div)
			self._clean_article()
 			if self.article['title']:
				self.handle_article(self.article)


	def _parse_article(self, div):
		self.article = ScholarArticle()

		for tag in div:
			if not hasattr(tag, 'name'):
				continue

			if tag.name == 'div' and self._tag_has_class(tag, 'title') and tag.a:
				self.article['title'] = ''.join(tag.a.findAll(text=True))
				self.article['url'] = self._path2url(tag.a['href'])
				continue

			
			if tag.name == 'div' and self._tag_has_class(tag, 'source'):
				spans = tag.findAll('span')
				if len(spans) != 2:
					continue

				if self._tag_has_class(spans[0], 'publicationDate'):
					self.article['date']  = ''.join(spans[0].findAll(text=True))
				
				self.article['conference'] = ''.join(spans[1].findAll(text=True))

			if tag.name == 'div' and self._tag_has_class(tag, 'metrics'):
				tags = tag.findAll('div')
				if len(tags) < 2:
					continue
				div = tags[1]

				if self._tag_has_class(div, 'metricsCol2') and div.div and div.div.span and self._tag_has_class(div.div.span, 'citedCount'):
					#print ''.join(div.div.span.findAll(text=True))
					match = self.citation.match(''.join(div.div.span.findAll(text=True)))
					if match:
						self.article['num_citations'] = int(match.group(1))


		#print self.article.as_txt()
				

	@staticmethod
	def _tag_has_class(tag, klass):
		"""
		This predicate function checks whether a BeatifulSoup Tag instance
		has a class attribute.
		"""
		res = tag.get('class') or []
		if type(res) != list:
 			# BeautifulSoup 3 can return e.g. 'gs_md_wp gs_ttss',
			# so split -- conveniently produces a list in any case
			res = res.split()
		return klass in res

	@staticmethod
	def _tag_contain_article(tag):
		return tag.name == 'div' and ScholarArticleParser._tag_has_class(tag, 'details')	

	def _path2url(self, path):
		"""Helper, returns full URL in case path isn't one."""
		if path.startswith('http://'):
			return path
		if not path.startswith('/'):
			path = '/' + path
		return self.site + path


class ScholarQuerier(object):
	"""
	ScholarQuerier instances can conduct a search on Google Scholar
	with subsequent parsing of the resulting HTML content.  The
	articles found are collected in the articles member, a list of
	ScholarArticle instances.
	"""
	class Parser(ScholarArticleParser):
		def __init__(self, querier):
			ScholarArticleParser.__init__(self)
			self.querier = querier

		def handle_article(self, art):
			self.querier.add_article(art)

	def __init__(self):
		self.articles = []
		self.query = None
		self.cjar = MozillaCookieJar()

		# If we have a cookie file, load it:
		if ScholarConf.COOKIE_JAR_FILE and \
			os.path.exists(ScholarConf.COOKIE_JAR_FILE):
			try:
				self.cjar.load(ScholarConf.COOKIE_JAR_FILE, ignore_discard=True)
				ScholarUtils.log('info', 'loaded cookies file')
			except Exception as msg:
				ScholarUtils.log('warn', 'could not load cookies file: %s' % msg)
				self.cjar = MozillaCookieJar() # Just to be safe

		self.opener = build_opener(HTTPCookieProcessor(self.cjar))
		self.settings = None # Last settings object, if any


	def send_query(self, query):
		"""
		This method initiates a search query (a ScholarQuery instance)
		with subsequent parsing of the response.
		"""
		self.clear_articles()
		self.query = query

		html = self._get_http_response(url=query.get_url(),
										log_msg='dump of query response HTML',
										err_msg='results retrieval failed')
		if html is None:
			return

		#print len(html)

		self.parse(html)


	def parse(self, html):
		"""
		This method allows parsing of provided HTML content.
		"""
		parser = self.Parser(self)
		parser.parse(html)


	def add_article(self, art):
		#self.get_citation_data(art)
		self.articles.append(art)

	def clear_articles(self):
		"""Clears any existing articles stored from previous queries."""
		self.articles = []

	def _get_http_response(self, url, log_msg=None, err_msg=None):
		"""
		Helper method, sends HTTP request and returns response payload.
		"""
		if log_msg is None:
			log_msg = 'HTTP response data follow'
		if err_msg is None:
			err_msg = 'request failed'
		try:
			ScholarUtils.log('info', 'requesting %s' % unquote(url))

			req = Request(url=url, headers={'User-Agent': ScholarConf.USER_AGENT})
			hdl = self.opener.open(req)
			html = hdl.read()

			ScholarUtils.log('debug', log_msg)
			ScholarUtils.log('debug', '>>>>' + '-'*68)
			ScholarUtils.log('debug', 'url: %s' % hdl.geturl())
			ScholarUtils.log('debug', 'result: %s' % hdl.getcode())
			ScholarUtils.log('debug', 'headers:\n' + str(hdl.info()))
			ScholarUtils.log('debug', 'data:\n' + html.decode('utf-8')) # For Python 3
			ScholarUtils.log('debug', '<<<<' + '-'*68)

			return html
		except Exception as err:
			ScholarUtils.log('info', err_msg + ': %s' % err)
			return None


class SearchScholarQuery():
	def __init__(self):
		self.sTitle = None 
		self.sYear = None

	def set_title(self, sTitle):
		"""Sets words that *all* must be found in the title."""
		self.sTitle = sTitle

	def set_year(self, year):
		self.sYear = year

	def get_url(self):
		self.sTitle = self.sTitle.replace(':', '')
		self.sTitle = self.sTitle.replace('+', '%252B')
		wordList = self.sTitle.split()

		sURL = 'http://dl.acm.org/results.cfm?query=acmdlTitle:('

		for word in wordList:
			sURL += '%252B'
			sURL += word
			sURL += '%20'

		if len(wordList) > 0:
			sURL = sURL[:-3]

		sURL += ')&within=owners.owner=HOSTED&filtered=&dte='

		if self.sYear != None:
			sURL += self.sYear
		else:
			sURL += ""

		sURL += '&bfr='

		if self.sYear != None:
			sURL += self.sYear
		else:
			sURL += ""

		return sURL



def usage():
	print '-t', '--title', 'paper title'
	print '-y', '--year', 'when paper was published'



def main(argv):
	try:
		opts, args = getopt.getopt(argv, 't:y:', ['title==', 'year=='])
	except getopt.GetoptError:
		usage()
		sys.exit(2)


	sTitle = None
	sYear = None

	for opt, arg in opts:
		if opt in ('-t', '--title'):
			sTitle = arg
		elif opt in ('-y', '--year'):
			sYear = arg
		

	if sTitle == None :
		usage()
		sys.exit(2)

	querier = ScholarQuerier()
	query = SearchScholarQuery()

	query.set_title(sTitle)
	query.set_year(sYear)

	querier.send_query(query)

	txt(querier)

def txt(querier):
	articles = querier.articles
	for art in articles:
		print(encode(art.as_txt()) + '\n')

	





if __name__ == '__main__':
	#url = 'http://dl.acm.org/results.cfm?query=acmdlTitle:(%252Bunderstanding%20%252Band%20%252Bdetecting%20%252Breal-world%20%252Bperformance%20%252Bbugs)&within=owners.owner=HOSTED&filtered=&dte=&bfr='
	#cjar = MozillaCookieJar()
	#opener = build_opener(HTTPCookieProcessor(cjar))
	#req = Request(url=url, headers={'User-Agent': ScholarConf.USER_AGENT})
	#hdl = opener.open(req)
	#html = hdl.read()

	#print html
	#fHTML = open(sys.argv[1], 'r')
	#sHTML = fHTML.read()
	#fHTML.close()

	#parser = ScholarArticleParser()

	#parser.parse(sHTML)

	main(sys.argv[1:])
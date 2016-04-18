import optparse
import os
import sys
import re

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

	VERSION = '2.10'
	LOG_LEVEL = 1
	MAX_PAGE_RESULTS = 20 # Current maximum for per-page results
	SCHOLAR_SITE = 'http://scholar.google.com'

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
			'year':          [None, 'Year',           2],
			'num_citations': [0,    'Citations',      3],
			'num_versions':  [0,    'Versions',       4],
			'cluster_id':    [None, 'Cluster ID',     5],
			'url_pdf':       [None, 'PDF link',       6],
			'url_citations': [None, 'Citations list', 7],
			'url_versions':  [None, 'Versions list',  8],
			'url_citation':  [None, 'Citation link',  9],
			'excerpt':       [None, 'Excerpt',       10],
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

	def as_csv(self, header=False, sep='|'):
		# Get keys sorted in specified order:
		keys = [pair[0] for pair in \
			sorted([(key, val[2]) for key, val in list(self.attrs.items())],
				key=lambda pair: pair[1])]
		res = []
		if header:
			res.append(sep.join(keys))
		res.append(sep.join([unicode(self.attrs[key][0]) for key in keys]))
		return '\n'.join(res)

	def as_citation(self):
		"""
		Reports the article in a standard citation format. This works only
		if you have configured the querier to retrieve a particular
		citation export format. (See ScholarSettings.)
		"""
		return self.citation_data or ''


#!/usr/bin/python
#	vim:fileencoding=utf-8
# vim modeline parsing module.
# (c) 2012 Michał Górny <mgorny@gentoo.org>
# Released under the terms of the 2-clause BSD license.

"""
Vim modeline parsing module.

>>> from pprint import pprint
>>> p = ModelineParser()
>>> pprint(p.parse_line('// vi:syntax=perl:fileencoding=utf8:'))
{'fileencoding': 'utf8', 'syntax': 'perl'}
>>> pprint(p.parse_line('vi:syntax=perl'))
{'syntax': 'perl'}
>>> pprint(p.parse_line('# ex:syntax=perl fileencoding=utf8:textwidth=40'))
{'fileencoding': 'utf8', 'syntax': 'perl', 'textwidth': '40'}
>>> pprint(p.parse_line('ex:syntax=perl'))
{}
>>> pprint(p.parse_line('#vim:syntax=python'))
{}
>>> pprint(p.parse_line('/* vim:set syntax=perl fileencoding=utf8 : */'))
{'fileencoding': 'utf8', 'syntax': 'perl'}
>>> pprint(p.parse_line('// vim:se syntax=python:fileencoding=utf8'))
{'syntax': 'python'}
>>> pprint(p.parse_line('<!-- vim:se syntax=python fileencoding=utf8:'))
{'fileencoding': 'utf8', 'syntax': 'python'}
>>> pprint(p.parse_line('# vim:se syntax=python fileencoding=utf8'))
{}
>>> pprint(p.parse_line('vim>0:syntax=perl'))
{'syntax': 'perl'}
>>> pprint(p.parse_line('vi>0:syntax=perl'))
{}
>>> pprint(p.parse_line('vim<100:syntax=perl'))
{}
"""

import re

class ModelineParser(object):
	"""
	A parser for vim modelines.
	"""

	_modelines = 5
	_vim_version = 730

	@property
	def modelines(self):
		"""
		The number of lines at the beginning or the end of file which
		are tested for modelines.

		Defaults to 5.
		"""
		return _modelines

	@modelines.setter
	def modelines(self, new_val):
		_modelines = new_val

	@property
	def vim_version(self):
		"""
		The 'emulated' vim version.

		This will be used when processing a versioned modeline in order
		to check it should be applied. It defaults to the vim version
		used to create the option mapping table.

		Usually, a three-digit version number should be supplied here
		(730 for vim 7.3). If you need a more specific matching logic,
		you can use any object implementing __lt__, __gt__ and __eq__
		comparisons against an integer.
		"""

		return self._vim_version

	@vim_version.setter
	def vim_version(self, new_val):
		self._vim_version = new_val

	def parse_buffer(self, buf):
		"""
		Parse the modelines from buffer.

		Returns a dict with options and their values.
		"""

		# Note: 'modelines' option in modeline does not affect modeline
		# parsing, so we can treat that as const.
		mls = self._modelines
		ret = dict()

		# XXX: replace it with something more efficient. And prevent
		# parsing the same lines twice.
		for l in buf.splitlines()[:mls]:
			ret.update(self.parse_line(l))
		for l in buf.splitlines()[-mls:]:
			ret.update(self.parse_line(l))

		return ret

	_form1_re = re.compile(r'''
		^

		(?:
			# vi: or vim: either on start-of-line or following
			# whitespace.
			(?: .*? \s+ )?
			(?: vi (?P<has_vim> m )? )

			# or ex: following whitespace.
			| .*? \s+ ex
		)

		# optionally, a version requirement
		# but only for 'vim'
		(?(has_vim)
			(?P<version_op> [<=>] )?
			(?P<version_no> \d* )
		)

		:

		# an optional whitespace.
		\s*

		# but no 'se' or 'set' as that would engage form2 matching.
		# we need to check that explicitly to avoid treating
		# unterminated form2 as form1.
		(?! se t? \s)

		# the remaining part of the line contains options then.
		(?P<options> .* )

		$
	''', re.VERBOSE)

	_form2_re = re.compile(r'''
		^

		(?:
			# vi: or vim: either on start-of-line or following
			# whitespace.
			(?: .*? \s+ )?
			(?: vi (?P<has_vim> m )? )

			# or ex: following whitespace.
			| .*? \s+ ex
		)

		# optionally, a version requirement
		# but only for 'vim'
		(?(has_vim)
			(?P<version_op> [<=>] )?
			(?P<version_no> \d* )
		)

		:

		# an optional whitespace.
		\s*

		se t?

		\s+

		# the remaining part of the line contains options then.
		(?P<options>
			(?: [^:] | : (?<= \\ ) )+
		)

		# and they *must* end with a :
		:
	''', re.VERBOSE)

	# it can be common to both forms since in form2 unescaped :
	# acts as end-of-modeline.
	_option_split_re = re.compile(r'''
		# either space or : but not preceded by a backslash.
		(?<! \\ ) [:\s]+
	''', re.VERBOSE)

	_option_unescape_re = re.compile(r'''
		# space or :, preceded by a backslash.
		\\ ( [:\s] )
	''', re.VERBOSE)

	def parse_line(self, l):
		"""
		Parse a single line for a modeline.

		Returns a dict with options and their values.
		"""

		ret = {}

		m = self._form2_re.match(l) or self._form1_re.match(l)
		if m:
			applies = False

			ver_no = int(m.group('version_no') or '0')
			ver_op = m.group('version_op')
			if ver_op == '>':
				applies = self._vim_version > ver_no
			elif ver_op == '=':
				applies = self._vim_version == ver_no
			elif ver_op == '<':
				applies = self._vim_version < ver_no
			else:
				applies = self._vim_version >= ver_no

			if not applies:
				return ret

			for o in re.split(self._option_split_re, m.group('options')):
				kv = o.split('=', 1)
				key = kv[0]

				if not key:
					continue

				if len(kv) > 1:
					value = self._option_unescape_re.sub(r'\1', kv[1])
				else:
					value = True

				ret[key] = value

		return ret

"""
Packaging script for PyPI.
"""
import os, setuptools
from pathlib import Path

_grammar_source = Path(__file__).parent / "sophie" / "Sophie.md"
if _grammar_source.exists():
	from boozetools.macroparse.runtime import make_tables
	make_tables(_grammar_source)

setuptools.setup(
	name='sophie-lang',
	author='Ian Kjos',
	author_email='kjosib@gmail.com',
	version='0.0.0',
	packages=['sophie', "sophie.adapters", ],
	package_data={
		'sophie': ["Sophie.automaton"]+["sys/"+f for f in os.listdir("sophie/sys")],
	},
	license='MIT',
	description='A call-by-need strong-inferred-type language named for French mathematician Sophie Germain',
	long_description=open('README.md').read(),
	long_description_content_type="text/markdown",
	url="https://github.com/kjosib/sophie",
	classifiers=[
		"Programming Language :: Python :: 3.9",
		"License :: OSI Approved :: MIT License",
		"Operating System :: OS Independent",
		"Development Status :: 3 - Alpha",
		"Intended Audience :: Developers",
		"Intended Audience :: Education",
		"Topic :: Software Development :: Interpreters",
		"Topic :: Software Development :: Compilers",
		"Topic :: Education",
		"Environment :: Console",
    ],
	python_requires='>=3.9',
	install_requires=[
		"booze-tools>=0.6.1.0",
		"pygame>=2.4.0",
	]
)
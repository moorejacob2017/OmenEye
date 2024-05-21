# setup.py

from setuptools import setup, find_packages

setup(
    name='OmenEye',
    version='0.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'omeneye=OmenEye.omeneye_cli:cli',
            #'omenparse=OmenEye.parser_cli:parse',
        ]
    },
    install_requires=[
        'requests',
        'mitmproxy',
        'beautifulsoup4',
        'asyncio',
        'chardet',
        'feedparser',
    ],
    author='Jacob Moore',
    author_email='moorejacob2017@gmail.com',
    description='',
    #long_description=open('description.md').read(),
    #long_description_content_type='text/markdown',
    url='https://github.com/moorejacob2017/',
    license='MIT',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
        #'Operating System :: POSIX :: Linux',
    ],
    keywords='',
)
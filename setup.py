# setup.py

from setuptools import setup, find_packages

setup(
    name='OmenEye',
    version='0.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'omeneye=OmenEye.omeneye_cli:cli',
            'oeparse=OmenEye.omeneye_parse_cli:cli',
        ]
    },
    install_requires=[
        'requests',
        'beautifulsoup4',
        'asyncio',
        'chardet',
        'feedparser',
        'selenium>=4.21.0'
    ],
    author='Jacob Moore',
    author_email='moorejacob2017@gmail.com',
    description='',
    #long_description=open('description.md').read(),
    #long_description_content_type='text/markdown',
    url='https://github.com/moorejacob2017/OmenEye',
    license='MIT',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Operating System :: OS Independent',
        #'Operating System :: POSIX :: Linux',
    ],
    keywords='',
)
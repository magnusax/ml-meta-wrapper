from setuptools import setup, find_packages

setup(
  name='gazer',
  version='0.1.dev1',
  description='Machine learning library built on top of several popular projects, e.g., scikit-learn and scikit-optimize.',
  author='Magnus Axelsson',
  author_email='johanmagnusaxelsson@gmail.com',
  url='https://github.com/magnusax/ml-meta-wrapper', # use the URL to the github repo
  keywords=['machine learning', 'software'], # arbitrary keywords
  install_requires=["numpy", "scipy", "scikit-learn>=0.17", "seaborn", "skopt>=0.3"],
  license='MIT License',
  classifiers=[
    'Development Status :: 3 - Alpha',
    'Intended Audience :: Developers',
    'Topic :: Software Development :: Machine Learning',
    'License :: OSI Approved :: MIT License',
    'Programming Language :: Python :: 3.4',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6'
  ],
  packages=find_packages(),
)
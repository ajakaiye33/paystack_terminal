from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

setup(
	name="paystack_terminal",
	version="1.0.0",
	description="Paystack Terminal Integration for ERPNext Healthcare",
	author="Gemutanalytics",
	author_email="dev@gemutanalytics.com",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)

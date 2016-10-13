from setuptools import setup

setup(
    name='tupler',
    version='0.0.1',
    packages=[
        'tupler',
    ],
    zip_safe=False,
    entry_points={
        'console_scripts': [
            'tupler = tupler.tupler_main:main'
        ]
    }
)

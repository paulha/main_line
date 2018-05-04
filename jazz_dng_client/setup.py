from distutils.core import setup

install_requires = {
    'PyYAML',
    'pysocks',
    'lxml',
    'requests',
    'git+http://github.com/paulha/utility_funcs.git',
}

setup(
    name='jazz_dng_client',
    version='0.1',
    packages=[''],
    package_dir={'': '../jazz_dng_client'},
    url='',
    license='',
    author='paulhanchett',
    author_email='paul.hanchett@gmail.com',
    description=''
)

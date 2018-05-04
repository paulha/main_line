from distutils.core import setup

install_requires = {
    'json',
    'requests',
    'git+http://github.com/paulha/utility_funcs.git',
}

setup(
    name='jama_client',
    version='0.1',
    packages=[''],
    package_dir={'': '../jama_client'},
    url='',
    license='',
    author='paulhanchett',
    author_email='paul.hanchett@gmail.com',
    description=''
)

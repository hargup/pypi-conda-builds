from __future__ import print_function
from compile_report import compile_all_reports
from os.path import isdir
# XXX: urllib2 is not availabe on python 3
import urllib2
import json
import argparse
import subprocess
import yaml
import shlex
import sys
if sys.version_info < (3,):
    from xmlrpclib import ServerProxy, Transport, ProtocolError
else:
    from xmlrpc.client import ServerProxy


parser = argparse.ArgumentParser()
parser.add_argument("-n",
                    help="Number of packages",
                    type=int)
parser.add_argument("--start-over",
                    help="Remove all the current information and packages",
                    action="store_true")
parser.add_argument("--recipe",
                    help="Creates recipes for the specified packages",
                    action="store_true")
parser.add_argument("--build",
                    help="Build packages for the available recipes",
                    action="store_true")
parser.add_argument("--pipbuild",
                    help="pipuild packages",
                    action="store_true")
parser.add_argument("--packages",
                    help="List of names of packags to create",
                    nargs="+",
                    action="store")
parser.add_argument("--all",
                    help="Apply process at all the packages including the ones"
                         " those passed in earlier builds",
                    action="store_true")
args = parser.parse_args()


def create_recipe(package, recipes_data):
    log_file_name = log_dir + "%s_recipe.log" % (package)
    log_file = open(log_file_name, 'w')

    if package not in recipes_data.keys():
        recipes_data[package] = dict()

    msg = "Creating Conda recipe for %s\n" % (package)
    print(msg)

    # Remove the old recipe
    if not isdir(recipes_dir + package):
        cmd = "conda skeleton pypi %s --output-dir %s" \
            " --recursive --no-prompt --all-extras --noarch-python"
        cmd = cmd % (package, recipes_dir)
        err = subprocess.call(shlex.split(cmd), stdout=log_file,
                              stderr=subprocess.STDOUT)
    else:
        err = 0
        print("Recipe already available")

    if err is 0:
        msg = "Succesfully created conda recipe for %s\n" % (package)
        recipes_data[package]['recipe_available'] = True
    else:
        msg = "Failed to create conda recipe for %s\n" % (package)
        recipes_data[package]['recipe_available'] = False
        print(msg)
    log_file.close()


def build_recipe(package, build_data, packages_data):
    log_file_name = log_dir + "%s_build.log" % (package)
    log_file = open(log_file_name, 'w')

    if package not in build_data.keys():
        build_data[package] = dict()

    msg = "Building Conda recipe for %s\n" % (package)
    print(msg)

    cmd = "conda build %s" % (recipes_dir + package)
    err = subprocess.call(shlex.split(cmd), stdout=log_file,
                          stderr=subprocess.STDOUT)

    if err is 0:
        msg = "Succesfully build conda package for %s\n" % (package)
        build_data[package]['build_successful'] = True
        packages_data[package]['package_available'] = True
        packages_data[package]['availability_type'] = 'conda-build'
    else:
        msg = "Failed to build conda package for %s\n" % (package)
        build_data[package]['build_successful'] = False
    print(msg)
    log_file.close()


def pipbuild(package, pipbuild_data, packages_data):
    log_file_name = log_dir + "%s_pipbuild.log" % (package)
    log_file = open(log_file_name, 'w')

    if package not in pipbuild_data.keys():
        pipbuild_data[package] = dict()

    msg = "Creating Conda recipe for %s using pipbuild\n" % (package)
    print(msg)

    cmd = "conda pipbuild %s --noarch-python" % (package)
    err = subprocess.call(shlex.split(cmd), stdout=log_file,
                          stderr=subprocess.STDOUT)

    if err is 0:
        msg = "Succesfully created conda package for %s\n" % (package)
        pipbuild_data[package]['pipbuild_successful'] = True
        packages_data[package]['package_available'] = True
        packages_data[package]['availability_type'] = 'pipbuild'
    else:
        msg = "Failed to create conda package for %s\n" % (package)
        pipbuild_data[package]['pipbuild_successful'] = False
    print(msg)
    log_file.close()


def save_data():
    yaml.dump(packages_data, open('packages_data.yaml', 'w'))
    yaml.dump(recipes_data, open('recipes_data.yaml', 'w'))
    yaml.dump(build_data, open('build_data.yaml', 'w'))
    yaml.dump(pipbuild_data, open('pipbuild_data.yaml', 'w'))


def clean_data():
    unclean_pkgs = [pkg for pkg in recipes_data
                    if recipes_data[pkg]['recipe_available'] is None]
    for pkg in unclean_pkgs:
        recipes_data.pop(pkg)

    unclean_pkgs = [pkg for pkg in build_data
                    if build_data[pkg]['build_data_successful'] is None]
    for pkg in unclean_pkgs:
        build_data.pop(pkg)

    # for pkg in pipbuild:
    #     if pipbuild[pkg]['pipbuild_successful'] is None:
    #         pipbuild.pop(pkg)

    save_data()


def reorganise_old_format(packages_old, packages, recipes, build):
    for package in packages_old:
        package_available = False
        availability_type = None
        if package['anaconda']:
            package_available = True
            availability_type = "Anaconda"
        elif package['build']:
            package_available = True
            availability_type = "conda-build"

        packages[package['name']] = {'package_available': package_available,
                                     'availability_type': availability_type}

        recipes[package['name']] = {'recipe_available': package['recipe']}
        build[package['name']] = {'build_successful': package['build']}


def get_packages_list(n):
    """
    Gives the list of top n packages sorted by download count
    """
    return [pkg.lower() for (pkg, downloads) in client.top_packages(n)]


def get_previous_build_timestamp():
    """
    Return the time of previous build in second since Epoch[1]. Returns 0 if
    timestamp file is not available

    [1]: https://en.wikipedia.org/wiki/Unix_time

    """
    file_name = 'timestamp'
    try:
        timestamp = int(open(file_name, 'r').readline().strip())
    except IOError:
        timestamp = 0

    return timestamp


def save_timestamp():
    """
    Save the current timestamp to file 'timestamp'
    """
    import time
    file_name = 'timestamp'
    with open(file_name, 'w') as timestamp_file:
        # PyPI's XMLRPC interface expects the value in int, time.time retuns a
        # float.
        timestamp_file.write(str(int(time.time())))


def yaml_load(file_name, default=None):
    """
    Load a yaml file given a filename, returns default if file doesn't exists.
    """
    try:
        res = yaml.load(open(file_name, 'r'))
    except IOError:
        res = default

    return res


def get_repo_packages():
    # TODO: Only skipping linux-64 packages for now, add packages from other
    # repos and probably take an intersection of them.
    linux64_url = 'https://repo.continuum.io/pkgs/free/linux-64/repodata.json'
    return parse_repodata_json(linux64_url)


def parse_repodata_json(url):
    jsonurl = urllib2.urlopen(url)
    data = json.loads(jsonurl.read())
    pkgs = set([data[u'packages'][src][u'name']
                for src in data[u'packages'].keys()])
    return pkgs

pypi_url = 'http://pypi.python.org/pypi'
client = ServerProxy(pypi_url)

log_dir = "./logs/"
recipes_dir = "./recipes/"

repo_packages = get_repo_packages()
greylist_packages = set(yaml_load('greylist.yaml', default=[]))
packages_data = yaml_load('packages_data.yaml', dict())
recipes_data = yaml_load('recipes_data.yaml', dict())
build_data = yaml_load('build_data.yaml', dict())
pipbuild_data = yaml_load('pipbuild_data.yaml', dict())


def main(args):
    if args.n:
        top_n_packages = set(get_packages_list(args.n))
    else:
        top_n_packages = set()

    if args.all:
        old_pkgs = packages_data.keys()
    else:
        changed_pkgs = set(client.changed_packages(get_previous_build_timestamp()))
        # Include old failed or changed packages
        old_pkgs = set(pkg for pkg in packages_data if
                       packages_data[pkg]['package_available'] is not True or
                       pkg in changed_pkgs)

    candidate_packages = top_n_packages.union(old_pkgs) \
        - (repo_packages.union(greylist_packages))

    for pkg in repo_packages:
        if pkg not in packages_data.keys():
            packages_data[pkg] = dict()
        packages_data[pkg]['package_available'] = True
        packages_data[pkg]['availability_type'] = 'repo.continuum.io'


    # TODO: complete the part where list of packages is passed through
    # commandline
    for pkg in candidate_packages:
        if pkg not in packages_data.keys():
            packages_data[pkg] = dict()
        packages_data[pkg]['package_available'] = False
        packages_data[pkg]['availability_type'] = None

        if args.recipe:
            create_recipe(pkg, recipes_data)

        if args.build:
            build_recipe(pkg, build_data, packages_data)

        if args.pipbuild:
            if packages_data[pkg]['package_available']:
                print("Package already available through conda-build")
            else:
                pipbuild(pkg, pipbuild_data, packages_data)


if __name__ == "__main__":
    try:
        main(args)
    except KeyboardInterrupt:
        print("Process Interrupted by User")
    finally:
        save_timestamp()
        save_data()
        compile_all_reports()

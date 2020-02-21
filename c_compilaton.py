import json
import subprocess
import optparse
import sys
import os
import shutil
import glob

def create_tar():
    os.chdir("/home/hemalatha/py-learn/script")
    cmd  = "tar cvf makefile.tar munich"
    subprocess.run(cmd,stderr=subprocess.PIPE,stdout=subprocess.PIPE,shell=True)
    os.listdir("/home/hemalatha/py-learn/script")
    for i in glob.iglob("*.tar"):
        print(i)
def build_generate(cfg):
    cmd = "git clone -b development git@github.com:khavyashreeyadam/practicerepository.git /home/hemalatha/py-learn/script"
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    shutil.rmtree("/home/hemalatha/py-learn/script")
    os.mkdir("/home/hemalatha/py-learn/script")
    os.chdir("/home/hemalatha/py-learn/script")
    pw = os.getcwd()
    print(os.listdir(pw))
    os.system("make")

def has_chage():
    cmd = "git ls-remote git@github.com:khavyashreeyadam/practicerepository.git  | grep development | awk '{print$1}'  "
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,shell=True)
    o, e = p.communicate()
    has_change1 = o.decode('ascii')
    return has_change1


def record_keeping(cfg, version,commit):
    cfg['commit']['development'] = commit
    version1 = version.split('.')
    version1[-1] = int(version1[-1]) + 1
    version1[-1] = str(version1[-1])
    version1 = '.'.join(version1)
    cfg['version']['development'] = version1
    print(cfg['commit']['development'])
    print(cfg['version']['development'])
    return cfg



def main():
    f = open("version.json", "r")
    cfg = json.load(f)
    # check is there any change in gitub code.
    # if change is present, start build otherwise exit.
    commitid = has_chage()
    if commitid:
        print("Able to get commit id")
    else:
        print("Unable to get commit id")
    commitid_previous = cfg['commit']['development']
    if commitid == commitid_previous:
        print("No changes from repo")
        sys.exit(0)
    else:
        print("Changes are there in git, so continuing build")

    #Get the Build version from version.json (version + commitid)
    print((commitid[:6]))
    version = cfg['version']['development']
    print(version)
    s="-"
    seq = (version,commitid[:6])
    build_version = s.join(seq)
    print(build_version)
    path = "/home/hemalatha/py-learn/cdir"
    pa = os.path.exists(path)
    print(pa)
    if pa:
        print("path is there ok good")
    else:
        os.mkdir("/home/hemalatha/py-learn/cdir")

    muni = record_keeping(cfg, version, commitid)
    file = open("version.json", "w")
    json.dump(muni, file)
    build_generate(cfg)
    create_tar()

if __name__ == "__main__":
    main()

#!/usr/bin/env python

import os	
import sys
import json
import optparse
import subprocess
import re
import time
import shutil
import glob

rebuild = False
# common options for svn command. 
#svnopts = "--username=svcacct-matdbuild"


def notify_error(cfg):
    bld_version = cfg['current_ver'] + '.' + cfg['gitcmt']
    mail_msg = "Build failed, for more information please view the build log.\n\n"
    log_path = os.path.join(cfg['top_log_url'],
                                 cfg['branch'],
                                 bld_version
                            )
    if cfg['comp']['win32']['error']:
        win32_log = os.path.join(log_path,
                                 "win32.bld.log")
        mail_msg = mail_msg + "win32 log: " + win32_log + "\n"
    if cfg['comp']['win64']['error']:
        win64_log = os.path.join(log_path,
                                 "win64.bld.log")
        mail_msg = mail_msg + "win64 log: " + win64_log + "\n"
    if cfg['comp']['android']['error']:
        android_log = os.path.join(log_path,
                                   "android-pdf.bld.log")
        mail_msg = mail_msg + "Android log: " + android_log + "\n"

    if cfg['engr_build']:
        mail_template = os.path.join("/tmp", 
                                     cfg['fail_mail_template']['engr'] + "." + str(os.getpid())
                                     )
        shutil.copy(cfg['fail_mail_template']['engr'], mail_template)
        subject = "Engineering build on %s %s FAIL" % \
            (cfg['central_host'], bld_version)
    else:
        mail_template = os.path.join("/tmp", 
                                     cfg['fail_mail_template']['rel'] + "." + str(os.getpid())
                                     )
        shutil.copy(cfg['fail_mail_template']['rel'], mail_template)
        subject = "Official build on %s %s FAIL" % \
            (cfg['central_host'], bld_version)
    # substitute the template for the subject and fail content log 
    mfh = file(mail_template, 'r+')
    mail_content = mfh.read()
    mail_content = re.sub("subject goes here", subject, mail_content)
    mail_content = re.sub("content goes here", mail_msg, mail_content)
    mfh.seek(0)
    mfh.write(mail_content)
    mfh.close()
    
    # send the mail
    cmd = "cat %s | sendmail -t" % mail_template
    os.system(cmd)

def has_changes(cfg):
    changes = False
    prevtag = get_prev_bldtag(cfg)
    if prevtag:
        tags = prevtag.split('_')
        prev_gitcmt = tags[-1]
        if prev_gitcmt != cfg['gitcmt']:
            changes = True
    else:
        print "fail to get previous tag"
    return changes

def source_copy(cfg):
   bld_version = cfg['current_ver'] + "." + cfg['gitcmt']
   copy_path = os.path.join(
        "/home/build/releases",
        cfg['branch'],
        bld_version,
        )
    os.chdir(copy_path)
    cmd = "cp -r /home/build/BUILD_MODULES/atd_github/ ."
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    out,error=p.communicate() 

def get_prev_bldtag(cfg):
    # Detect the previous tag given the type of build that we are 
    # about to make
    #global svnopts
    prevtag = None
    #repo = cfg['repo']
    #repo_tag_url = os.path.join(repo, "tags")
    prev_ver = cfg['prev_ver']
    cvs = prev_ver.split('.')
    product = cfg['product']
    if cfg['engr_build']:
        product = product + "e"
    bldid = int(cvs[-1])
    found = False
    while not found:
        search_svntag = product + "_" +  '_'.join(cvs) + "_" 
        print "searching for tag: ", search_svntag
        cmd = "git ls-remote --tags git@muni.git |grep '%s' |awk '{print $2}'| awk -F '/' '{print $3}'" % (search_svntag) 
        #cmd = "svn %s ls  %s | grep '^%s'" % (svnopts, repo_tag_url, search_svntag)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        prevtag, err = p.communicate()
        if prevtag:
            print prevtag
            print "found previos tag "
            return prevtag
        else:
            print "prevtag is not found"
    #return prevtag

def has_error(bld_log):

    status = False
    fh = file(bld_log)
    content = fh.read()
    if 'win32' in bld_log:
        # all win32 projects build use msdev and we search with pattern like 'error(s)'
        ms = re.findall(r'(.*)\s+-\s+(\d+) error\(s\)', content)
        for i in ms:
            p,rc = i[0],int(i[1])
            if rc != 0:
                print "Project ", p, "has build error"
                status = True
    elif 'win64' in bld_log:
        # search strategy, searching for devenv project and merge its result, search strategy for 
        # msdev projects like in win32 log
        m1devenv = re.findall('building: devenv.*', content)
        m2devenv = re.findall('Build succeeded|Build FAILED', content)
        m3devenv = zip(m1devenv, m2devenv)
        for i in m3devenv:
            p, rs = i
            if 'FAILED' in rs:
                print "Project ", p, "has build error"
                status = True
        ms = re.findall(r'(.*)\s+-\s+(\d+) error\(s\)', content)
        for i in ms:
            p,rc = i[0],int(i[1])
            if rc != 0:
                print "Project ", p, "has build error"
                status = True
    elif 'android' in bld_log:
        pass
    elif 'amas' in bld_log or \
            'nightly_build' in bld_log or \
            'output-build' in bld_log:
        ms=re.findall(r'(.*)\s+exit code:\s+(\d+)',content)
        for i in ms: 
            p,rc = i[0],int(i[1])
            if rc != 0:
                print "Project ", p, "has build error"
                status = True
                
    fh.close()    
    return status    


def package_msi_image(cfg):

    print "packaging msi images into its tar ball..."

    cp_msi_tool = "/home/jenkins/M_ATD/cp_avlab_img.py"
    bld_msi_tool = "/home/jenkins/M_ATD/bld_avlab_img.py"
    if cfg['engr_build']:
        tar_msi_config = "/home/jenkins/M_ATD/evebld.json"
    else:
        tar_msi_config = "/home/jenkins/M_ATD/vebld.json"

    bld_version = cfg['current_ver'] + "." + cfg['gitcmt']
    winxp_img = os.path.join(
        "/home/ve-build/releases",
        cfg['branch'],
        bld_version,
        cfg['comp']['win32']['image_loc']
        )
    win64_img = os.path.join(
        "/home/ve-build/releases",
        cfg['branch'],
        bld_version,
        cfg['comp']['win64']['image_loc']
        )
    cmd = "ssh jenkins@10.213.18.250 '%s --config %s --winxp-img %s --win64-img %s --bld-version %s'" % \
        (cp_msi_tool, tar_msi_config, winxp_img, win64_img, bld_version)
    print "executing: ", cmd
    rc = os.system(cmd)
    cmd = "ssh -t -t jenkins@10.213.18.250 'sudo %s %s'" % \
        (bld_msi_tool, bld_version)
    print "executing: ", cmd
    rc = os.system(cmd)
    return rc
    

def update_qa_automation_file(cfg):
    branch = cfg['branch']
    release_url = cfg['release_url']
    qa_automation_file = os.path.join(cfg['image_root'], branch, 'files.txt')
    fh = open(qa_automation_file, 'w')
    download_url = "http://%s/software/release%s" % \
        (
        cfg['comp']['amas']['bldhost'],
        release_url.replace(cfg['image_root'], '')
        )
    for f in os.listdir(release_url):
        f_abspath = os.path.join(release_url, f)
        if not os.path.isdir(f_abspath):
            if not os.path.islink(f_abspath):
                if 'msu' not in f and 'tgz' not in f:
                    if 'install-android' in f_abspath and \
                            branch not in cfg['old_release_branches']:
                        continue
                    
                    wget_path = os.path.join(download_url, f)
                    fh.write(wget_path + "\n")
    fh.close()


def record_keeping(cfg):
    product = cfg['product']
    branch = cfg['branch']
    prev_tag = get_prev_bldtag(cfg)
    if prev_tag:
        prev_version = '.'.join(prev_tag.split('_')[1:])
    bld_version = cfg['current_ver'] + "." + cfg['gitcmt']
    account_tool = cfg["account_tool"]
    if cfg['engr_build']:
        cmd = "ssh jenkins@10.213.18.250 '%s --product %s --branch %s --prev-buildid %s --current-buildid %s --engr-build'" % \
            (account_tool, 
             product, 
             branch, 
             prev_version, 
             bld_version
             )
    else:
        cmd = "ssh jenkins@10.213.18.250 '%s --product %s --branch %s --prev-buildid %s --current-buildid %s --ntba-url %s'" % \
            (account_tool, 
             product, 
             branch, 
             prev_version, 
             bld_version
             )
    
    print "Record keeping..."
    print "Executing: ", cmd
    rc = os.system(cmd)
    if rc == 0:
        print "Successfully record build information"
    else:
        print "Failed to record build information"


def msu_generate(cfg):
    bld_version = cfg['current_ver'] + "." + cfg['gitcmt']
    print bld_version
    branch = cfg['branch']
    print branch
    msupath=os.path.join(os.getenv('HOME'), "releases", branch, bld_version, "install", "Universal_Migration_Msu")
    print msupath
    os.chdir(msupath)
    os.system("make")
    os.system("make copy")

def iso_generate(cfg):
    bld_version = cfg['current_ver'] + "." + cfg['gitcmt']
    print bld_version
    branch = cfg['branch']
    print branch
    msupath=os.path.join(os.getenv('HOME'), "releases", branch, bld_version, "install", "MlosEasyInstaller")
    print msupath
    os.chdir(msupath)
    os.system("make iso")
    delfile='sudo '+'rm -f '+'/home/build/BUILD_MODULES/atd_iso/latest/ATD_installer.*.iso'
    os.system(delfile)
    #iso_name='ATD_installer.*.x86_64.iso'
    srcfile1=os.path.join(os.getenv('HOME'), "releases", branch, bld_version, "install", "MlosEasyInstaller")
    destfile1=os.path.join(os.getenv('HOME'), "BUILD_MODULES", "atd_iso", "latest")
    #shutil.copy(srcfile1, destfile1)
    files = glob.iglob(os.path.join(srcfile1, "*.iso"))
    for file in files:
        if os.path.isfile(file):
           shutil.copy2(file, destfile1)
    #os.system("make copy")

def gather_release_images(cfg):
    top_blddir = cfg['top_blddir']
    bld_version = cfg['current_ver'] + "." + cfg['gitcmt']
    bld_image_dir = os.path.join(top_blddir, "install/software/release")
    update_image_dir = os.path.join(top_blddir, "install/software/release/update-%s" % bld_version)
    amas_image = os.path.join(top_blddir, "install/AMAS", "amas-%s.bin" % bld_version)
    avengine_image = os.path.join(top_blddir, "install/3rdParty", "avengines-%s.bin" % bld_version)
    avgti_image = os.path.join(top_blddir, "install/3rdParty", "av-gti-%s.bin" % bld_version)
    sysconfig_image = os.path.join(top_blddir, "install/package", "system-config-%s.bin" % bld_version)
    update_bin = os.path.join(top_blddir, "install", "update.bin")
    update_bin_tgz = os.path.join(top_blddir, "install", "update.bin.tgz")
    update_msu = os.path.join(top_blddir, "install", "update.msu")

    images = [amas_image, avengine_image, avgti_image, sysconfig_image]
    update_images = [update_bin, update_bin_tgz, update_msu]

    if not os.path.exists(update_image_dir):
        os.makedirs(update_image_dir)

    for f in images:
        if os.path.exists(f):
            shutil.copy(f, bld_image_dir)
        else:
            print "missing image: ", f
    for f in update_images:
        if os.path.exists(f):
            shutil.copy(f, update_image_dir)
        else:
            print "missing image: ", f


def copy_img_download_path(cfg):
    image_root = cfg['image_root']
    top_blddir = cfg['top_blddir']
    bld_image_dir = os.path.join(top_blddir, "install/software/release")
    bld_version = cfg['current_ver'] + "." + cfg['gitcmt']
    releases = cfg['current_ver'].split('.')
    relver = '.'.join(releases[:-1])
    release_image_dir = os.path.join(image_root, cfg['branch'], relver, bld_version)
    print "release_image_dir: ", release_image_dir
    print "bld_image_dir: ", bld_image_dir

    if not os.path.exists(release_image_dir):
        os.makedirs(release_image_dir)

    for f in os.listdir(bld_image_dir):
        if os.path.exists(f):
            if os.path.isdir(f):
                shutil.copytree(f, os.path.join(release_image_dir, f))
            else:
                shutil.copy(f, release_image_dir)
    

def record_last_build(cfg):
    '''
    record last build id
    record the last msi package path
    '''
    #global svnopts
    current_ver = cfg['current_ver']
    branch = cfg['branch']
    release_ver = cfg['release_ver']
    version_file = os.path.join(os.getenv('HOME'), '.scm', 'version.json')
    fh = file(version_file, 'r+')
    v_cfg = json.load(fh)
    v_cfg[release_ver][branch]['version'] = current_ver
    v_cfg[release_ver]['latest_version'] = current_ver
    if cfg['package_msi']:
        v_cfg[release_ver][branch]['msi'] = cfg['release_msi_path']
    if cfg['package_android']:
        v_cfg[release_ver][branch]['android'] = cfg['release_android_path']
    if cfg['package_pdf']:
        v_cfg[release_ver][branch]['pdf'] = cfg['release_pdfscanner_path']
    fh.seek(0)
    json.dump(v_cfg, fh, indent=4)
    fh.close()

def get_ntba_rev(cfg):
    ntba_source_dir = os.path.join(cfg['top_blddir'],
                                   "install/AMAS/source/External/SHASTA_BRANCH/ntbashare"
                                   )
    cmd = "svn %s info %s" % (svnopts, ntba_source_dir)
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    out,err = p.communicate()
    if out:
        m = re.search(r'Last Changed Rev: (\d+)', out)
        rev = m.group(1)
        return rev


def tag_build(cfg):
    ##global svnopts
    branch = cfg['branch']
    #repo = cfg['repo']
    product = cfg['product']
    if cfg['engr_build']:
        product = product + "e"

    current_vers = cfg['current_ver'].split('.')
    git_tag = product + "_" +  '_'.join(current_vers) + "_" + cfg['gitcmt']
    print "tag to be created is :", git_tag
    os.chdir("/home/build/BUILD_MODULES/atd_github/Advanced-Threat-Defense")
    cmd = "git tag %s" % git_tag
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    out,error=p.communicate()
    ret_status=p.returncode
    print "Return status is :", ret_status
    cmd1 = "git push origin %s " % git_tag
    p = subprocess.Popen(cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    out,error=p.communicate()
    rc=p.returncode
    if rc == 0:
        print "successfully create tag with:", cmd
    else:
        print "failed to  create tag with:", cmd
    return rc
    

def get_gitcmt(cfg):
    """
    given the svn path, return the svn's revision
    """
    global svnopts
    repo = cfg['repo']
    branch = cfg['branch']
    if branch == "trunk":
        cmds = ["/usr/bin/svn",
                svnopts, 
                "info", 
                os.path.join(repo, branch)
                ]
    else:
        cmds = ["/usr/bin/svn", 
                svnopts, 
                "info", 
                os.path.join(repo, "branches", branch)
                ]
    print "cmds: ", cmds
    p = subprocess.Popen(cmds, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (out,err) = p.communicate()
    m = re.search("Last Changed Rev:\s*([\d]*)", out)
    gitcmt = None
    if m:
        gitcmt = m.group(1)
    return gitcmt
    

def main():
    
    #global svnopts
    parser = optparse.OptionParser()
    parser.add_option('--config', action="store", dest="config_file")
    parser.add_option('--build-type', action="store", dest="build_type", default="opt")
    parser.add_option('--branch', action="store", dest="branch")
    #parser.add_option('--gitcmt', action="store", dest="gitcmt", default="HEAD")
    parser.add_option('--current-ver', action="store", dest="current_ver", default=None)
    parser.add_option('--prev-ver', action="store", dest="prev_ver", default=None)
    parser.add_option('--step', action="store", dest="step")
    parser.add_option('--release-ver', action="store", dest="release_ver")
    # Turn the default value to "True" when we are ready to keep separate
    # directories for each build.
    parser.add_option('--create-newdir', action="store_true", dest="is_newdir",
                      default=False) 
    parser.add_option('--tag', action="store_true", dest="create_tag",
                      default=False) 
    parser.add_option('--test-build', action="store_true", dest="test_build",
                      default=False) 
    parser.add_option('--rebuild', action="store_true", dest="rebuild",
                      default=False) 
    options, remainder = parser.parse_args()
    cfg_file = options.config_file
    branch = options.branch
    current_ver = options.current_ver
    prev_ver = options.prev_ver
    rebuild = options.rebuild
    is_newdir = options.is_newdir
    #gitcmt = options.gitcmt
    create_tag = options.create_tag
    test_build = options.test_build
    release_ver = options.release_ver

    cfg_fh = file(cfg_file)
    cfg = json.load(cfg_fh)
    # cfg['gitcmt'] = gitcmt
    #cfg['ntbarev'] = None
    cfg['cfg_file'] = cfg_file
    cfg['build_type'] = options.build_type
    cfg['branch'] = branch
    cfg['prev_ver'] = prev_ver
    cfg['current_ver'] = current_ver
    cfg['release_ver'] = release_ver
    cfg['rebuild'] = rebuild
    cfg['is_newdir'] = is_newdir
    cfg['gitcmt'] = None
    cfg['engr_build'] = False
    if os.environ.has_key('ENGR_BUILD'):
        cfg['engr_build'] = True

    cfg['base_tag'] = None
    if os.environ.has_key('BASE_TAG'):
        cfg['base_tag'] = os.environ.get('BASE_TAG')

    if current_ver is None:
        version_file = os.path.join(os.getenv('HOME'), '.scm', 'version.json')
        vcfg = json.load(file(version_file))
        pv = vcfg[release_ver]['latest_version']
        cfg['prev_ver'] = vcfg[release_ver][branch]['version']
        pvs = pv.split('.')
        bldid = str(int(pvs[-1]) + 1)
        current_ver = "%s.%s" % ('.'.join(pvs[:-1]), bldid) 
        
        print current_ver

    if current_ver:
        cfg['current_ver'] = current_ver
	commitid = None
    gitcmt = None
    cmd = "git ls-remote git@muni.git | grep '%s' | awk '{ print $1}'" % (cfg['branch'])
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
    commitid, err = p.communicate()
    if commitid:
       print "found commitid is: ", commitid
       gitcmt = commitid[0:6]
       print "gitcmt is :", gitcmt
       if gitcmt:
          cfg['gitcmt'] = gitcmt
       else:
          print "gitcmt is not able to find"
    else:
       print "Git commit not found"


    if not has_changes(cfg):
        if cfg['force_build']:
            print "Force build even though there are no changes"
        else:
            print "Don't build! There are no new changes" 
            sys.exit(0)
    else:
        print "There are changes since the last build, new build ..."

    cfg['package_msi'] = True
    print "There are changes in Windows - build windows msi"
    cfg['43capable'] = True
    cfg['package_android'] = False
    print "There are no changes in Android source - package the old Android version" 

    cfg['package_pdf'] = False

    cfg['build_xen'] = False
    print "There are no changes in xen - don't build"

    bld_version = cfg['current_ver'] + "." + cfg['gitcmt']
    if os.environ.has_key('BULLEYE_BUILD'):
        top_blddir = os.path.join(
            os.getenv('HOME'),
            "releases",
            cfg['branch'],
            "bulleye",
            bld_version
            )
    elif os.environ.has_key('COVERITY'):
        top_blddir = os.path.join(
            os.getenv('HOME'),
            "releases",
            cfg['branch'],
            "coverity",
            bld_version
            )
    else:
        top_blddir = os.path.join(
            os.getenv('HOME'),
            "releases",
            cfg['branch'],
            bld_version
            )

    release_version = bld_version.split('.')
    release_url = os.path.join(cfg['image_root'], 
                               branch,
                               '.'.join(release_version[:-2]),
                               bld_version,
                               cfg['build_type']
                               )
    cfg['release_url'] = release_url
    print "release url is :", release_url	
    # clear out duplicate build work-space to avoid build error
    if os.path.exists(release_url):
        shutil.rmtree(release_url)
    os.makedirs(release_url)
    for pcs in cfg['parallel_comp']:
        for sc in pcs:
            if sc != "intermission":
                if sc != "amas":
                    if sc == "android":
                        if cfg['43capable']:
                            cmd = "ssh %s@%s 'rm -rf %s'" % \
                                (cfg['comp'][sc]['43']['blduser'], 
                                 cfg['comp'][sc]['43']['bldhost'],
                                 os.path.join(cfg['comp'][sc]['43']['topblddir'],
                                              branch,
                                              bld_version
                                              )
                                 )
                        else:
                            cmd = "ssh %s@%s 'rm -rf %s'" % \
                                (cfg['comp'][sc]['23']['blduser'], 
                                 cfg['comp'][sc]['23']['bldhost'],
                                 os.path.join(cfg['comp'][sc]['23']['topblddir'],
                                              branch,
                                              bld_version
                                              )
                                 )
                    else:
                        cmd = "ssh %s@%s 'rm -rf %s'" % \
                            (cfg['comp'][sc]['blduser'], 
                             cfg['comp'][sc]['bldhost'],
                             os.path.join(cfg['comp'][sc]['topblddir'],
                                          branch,
                                          bld_version
                                          )
                             )
                else:    
                    cmd = "rm -rf %s" % top_blddir
                print "cleaning by removing potential existed directory: ", cmd
                os.system(cmd)


    build_processes = []
    log = {}
    rel_img_dir = os.path.join(top_blddir, cfg['rel_img_dir'])
    if not os.path.exists(rel_img_dir):
        os.makedirs(rel_img_dir)
    log_dir = top_blddir
    cfg['top_blddir'] = top_blddir

    for pcs in cfg['parallel_comp']:
        for sc in pcs:
            if sc == "intermission":
                # check built component for any failure
                if 'win32' in cfg['parallel_comp'][0] and \
                        'win64' in cfg['parallel_comp'][0]:
                    win32_bld_log = os.path.join(log_dir, "win32.bld.log")
                    win64_bld_log = os.path.join(log_dir, "win64.bld.log")
                    win32_bldstatus = has_error(win32_bld_log)
                    win64_bldstatus = has_error(win64_bld_log)
                    if not win32_bldstatus and \
                            not win64_bldstatus:
                        if cfg.has_key('package_msi') and cfg['package_msi']:
                            # package built component before carring on with the final build, ie, building amas
                            print "MSI winxp build successfully..."
                            print "MSI win64 build successfully..."
                            rc = package_msi_image(cfg)
                            if rc == 0:
                                print "MSI winxp build successfully..."
                                print "MSI win64 build successfully..."
                            else:
                                print "Failed to package MSI... Terminate build..."
                                sys.exit(1)
    
                            cmd = "scp jenkins@10.213.18.250:/tmp/VElabS-%s.tgz %s" % \
                                (bld_version, rel_img_dir)
                            os.system(cmd)

                            # copy the msi tgz file to release area
                            cfg['release_msi_path'] = os.path.join(release_url, "VElabS-%s.tgz" % bld_version)
                            cmd = "cp %s/VElabS-%s.tgz %s" % \
                                (rel_img_dir, bld_version, release_url)
                            rc = os.system(cmd)
                            if rc == 0:
                                print "successful copy msi image to release directory: ", release_url
                            else:
                                print "Error: fail to copy msi image to release directory: ", release_url

                        else:
                            # don't build msi - package pre-defined - previous good msi
                            # copy the specified version to rel_image_dir
                            msi_cfg_fh = file(os.path.join(os.getenv('HOME'), ".scm", "version.json"))
                            msi_cfg = json.load(msi_cfg_fh)
                            msi_cfg_fh.close()
                            cmd = "cp %s %s" % (msi_cfg[release_ver][branch]['msi'], rel_img_dir)
                            os.system(cmd)

                    else:
                        if win32_bldstatus:
                            cfg['comp']['win32']['error'] = True
                            print "MSI winxp failed to build..."
                        else:
                            print "MSI winxp build successfully..."
                        if win64_bldstatus:
                            cfg['comp']['win64']['error'] = True
                            print "MSI win64 failed to build..."
                        else:
                            print "MSI win64 build successfully..."
                        if win32_bldstatus or win64_bldstatus:    
                            print "ERROR: failed to build Windows MSI image(s). Exiting..."
                            #notify_error(cfg)
                            sys.exit(1)
                if 'android' in cfg['parallel_comp'][0]:
                    android_pdf_bldstatus = has_error(os.path.join(log_dir, "android-pdf.bld.log"))
                    if cfg['43capable']:
                        droid_blduser = cfg['comp']['android']['43']['blduser']
                        droid_bldhost = cfg['comp']['android']['43']['bldhost']
                        droid_topblddir = cfg['comp']['android']['43']['topblddir']
                    else:
                        droid_blduser = cfg['comp']['android']['23']['blduser']
                        droid_bldhost = cfg['comp']['android']['23']['bldhost']
                        droid_topblddir = cfg['comp']['android']['23']['topblddir']
                    if not android_pdf_bldstatus:
                        if cfg.has_key('package_android') and cfg['package_android']:
                            print "Android build successfully..."

                            for ext in ['bin', 'zip']:
                                if cfg['43capable']:
                                    if ext == 'zip':
                                        src_file = "android_solution/install-android.%s" % ext
                                    else: # bin file
                                        src_file = "android_solution/install-android-%s.%s" % \
                                            (cfg['comp']['android']['43']['version'], ext)
                                else:
                                    src_file = "android/solution/install-android.%s" % ext
                                dest_file = "install-android-%s.%s" % (bld_version, ext)

                                cmd = "scp %s@%s:%s %s" % \
                                    (droid_blduser,
                                     droid_bldhost,
                                     os.path.join(droid_topblddir,
                                                  branch,
                                                  bld_version,
                                                  src_file
                                                  ),
                                     os.path.join(rel_img_dir, dest_file)
                                     )
                                os.system(cmd)
                                # copy the image to release area as well
                                if ext == "bin":
                                    cfg['release_android_path'] = os.path.join(release_url, dest_file)
                                    cmd = "cp %s/%s %s" % \
                                        (rel_img_dir, dest_file, release_url)
                                    rc = os.system(cmd)
                                    if rc == 0:
                                        print "successful copy android bin image to release directory: ", release_url
                                        save_cwd = os.getcwd()
                                        os.chdir(release_url)
                                        symlink_file = "install-android.bin"
                                        if os.path.exists(symlink_file):
                                            os.remove(symlink_file)
                                        os.symlink(dest_file, symlink_file)
                                        os.chdir(save_cwd)
                                    else:
                                        print "Error: fail to copy android image to release directory: ", release_url
                        else:
                            # don't build android - package pre-defined - previous android
                            # copy the specified version to rel_image_dir
                            android_cfg_fh = file(os.path.join(os.getenv('HOME'), ".scm", "version.json"))
                            android_cfg = json.load(android_cfg_fh)
                            android_cfg_fh.close()
                            cmd = "cp %s %s" % (android_cfg[release_ver][branch]['android'], rel_img_dir)
                            os.system(cmd)
                            cmd = "cp %s %s" % (android_cfg[release_ver][branch]['android'], release_url)
                            os.system(cmd)
                            save_cwd = os.getcwd()
                            os.chdir(release_url)
                            symlink_file = "install-android.bin"
                            if os.path.exists(symlink_file):
                                os.remove(symlink_file)
                            os.symlink(os.path.basename(android_cfg[release_ver][branch]['android']), symlink_file)
                            os.chdir(save_cwd)
                            

                        if cfg.has_key('package_pdf') and cfg['package_pdf']:
                            print "pdf-scanner build successfully..."
                            for ext in ['bin', 'zip']:
                                src_file = "pdf/install-pdfscanner.%s" % ext
                                dest_file = "install-pdfscanner-%s.%s" % (bld_version, ext)
                                cmd = "scp %s@%s:%s %s" % \
                                    (droid_blduser,
                                     droid_bldhost,
                                     os.path.join(droid_topblddir,
                                                  branch,
                                                  bld_version,
                                                  src_file
                                                  ),
                                     os.path.join(rel_img_dir, dest_file)
                                     )
                                os.system(cmd)
                                # copy the image to release area as well
                                if ext == "bin":
                                    cfg['release_pdfscanner_path'] = os.path.join(release_url, dest_file)
                                    cmd = "cp %s/%s %s" % \
                                        (rel_img_dir, dest_file, release_url)
                                    rc = os.system(cmd)
                                    if rc == 0:
                                        print "successful copy pdf-scanner bin image to release directory: ", release_url
                                        save_cwd = os.getcwd()
                                        os.chdir(release_url)
                                        symlink_file = "install-pdfscanner.bin"
                                        if os.path.exists(symlink_file):
                                            os.remove(symlink_file)
                                        os.symlink(dest_file, symlink_file)
                                        os.chdir(save_cwd)
                                    else:
                                        print "Error: fail to pdf-scanner image to release directory: ", release_url
                        else:
                            # don't build pdfscanner - package pre-defined - previous pdfscanner
                            # copy the specified version to rel_image_dir
                            pdfscanner_cfg_fh = file(os.path.join(os.getenv('HOME'), ".scm", "version.json"))
                            pdfscanner_cfg = json.load(pdfscanner_cfg_fh)
                            pdfscanner_cfg_fh.close()
                            cmd = "cp %s %s" % (pdfscanner_cfg[release_ver][branch]['pdf'], rel_img_dir)
                            os.system(cmd)
                            cmd = "cp %s %s" % (pdfscanner_cfg[release_ver][branch]['pdf'], release_url)
                            os.system(cmd)
                            save_cwd = os.getcwd()
                            os.chdir(release_url)
                            symlink_file = "install-pdfscanner.bin"
                            if os.path.exists(symlink_file):
                                os.remove(symlink_file)
                            os.symlink(os.path.basename(pdfscanner_cfg[release_ver][branch]['pdf']), symlink_file)
                            os.chdir(save_cwd)

                    else:
                        if (cfg.has_key('package_android') and cfg['package_android']) or \
                                (cfg.has_key('package_pdf') and cfg['package_pdf']):
                            print "Android/pdfscanner failed to build..."
                            print "ERROR: Android/pdfscanner failed to build. Exiting..."
                            cfg['comp']['android']['error'] = True
                            #notify_error(cfg)
                            sys.exit(1)
        
                break
            
            if sc == 'android':
                if cfg['43capable']:
                    bldhost = cfg['comp'][sc]['43']['bldhost']
                    blduser = cfg['comp'][sc]['43']['blduser']
                else:
                    bldhost = cfg['comp'][sc]['23']['bldhost']
                    blduser = cfg['comp'][sc]['23']['blduser']
            else:
                bldhost = cfg['comp'][sc]['bldhost']
                blduser = cfg['comp'][sc]['blduser']
            
            bldtool = os.path.join("/home", blduser, "comp_bld.py")
            config = os.path.join("/home", blduser, "vebld.json")
            cfg['comp'][sc]['error'] = False
        
            if sc == "amas":
                # add additional option to AMAS build 
                #if cfg['ntbarev']:
                 #   ntbarev_opt = " --ntba-rev %s" % cfg['ntbarev']
                #else:
                 #   ntbarev_opt = ""

                add_package_options = ""
                if cfg['package_msi']:
                    add_package_options = add_package_options + " --package-msi"
                if cfg['package_pdf']:
                    add_package_options = add_package_options + " --package-pdf"
                if cfg['package_android']:
                    add_package_options = add_package_options + " --package-android"
                if cfg['build_xen']:
                    add_package_options = add_package_options + " --build-xen"

                # for now - xen build in under amas. in the future, build it as a 
                # separate component.
                # check if we need to build xen
                #    building xen can be force by
                #      - change in source
                #      - change in configuration file

                    
                if test_build:
                   cmd = "env OFFICIAL_BUILD=1 TEST_BUILD=%s %s --comp %s --gitcmt %s --create-newdir --config %s --build-type %s --branch %s --release-ver %s --current-ver %s %s >& %s/%s.bld.log" % \
                       ("1", bldtool, sc, gitcmt, config, cfg['build_type'], branch, release_ver, current_ver, add_package_options, log_dir, sc)

                else:
                   cmd = "env OFFICIAL_BUILD=1 %s --comp %s --gitcmt %s --create-newdir --config %s --build-type %s --branch %s --release-ver %s --current-ver %s %s >& %s/%s.bld.log" % \
                       (bldtool, sc, gitcmt, config, cfg['build_type'], branch, release_ver, current_ver, add_package_options, log_dir, sc)

            elif sc == "win64" or sc =="win32":
                if cfg['package_msi']:
                    cmd = "ssh %s@%s 'env OFFICIAL_BUILD=1 %s --comp %s --gitcmt %s --create-newdir --config %s --branch %s --release-ver %s --current-ver %s' >& %s/%s.bld.log" % \
                        (blduser, bldhost, bldtool, sc, gitcmt, config, branch, release_ver, current_ver, log_dir, sc)
                else:
                    print "no changes in Windows code - handling "
                    # give a dummy command
                    cmd = "ssh %s@%s 'echo no-build' >& %s/%s.bld.log" % \
                        (blduser, bldhost, log_dir, sc)

            elif sc == "android":
                if cfg['package_android'] or cfg['package_pdf']:
                    android_pdf_options = ""
                    if cfg['package_android']:
                        android_pdf_options = "--package-android"
                    if cfg['package_pdf']:
                        android_pdf_options = android_pdf_options + " --package-pdf"
                    cmd = "ssh %s@%s 'env OFFICIAL_BUILD=1 %s --comp %s --gitcmt %s --create-newdir %s --config %s --branch %s --release-ver %s --current-ver %s' >& %s/%s-pdf.bld.log" % \
                        (blduser, bldhost, bldtool, sc, gitcmt, android_pdf_options, config, branch, release_ver, current_ver, log_dir, sc)
                else:
                    print "no changes in Android and pdfscanner code - handling "
                    # give a dummy command
                    cmd = "ssh %s@%s 'echo no-build' >& %s/%s-pdf.bld.log" % \
                        (blduser, bldhost, log_dir, sc)

            else:
                cmd = "ssh %s@%s 'env OFFICIAL_BUILD=1 %s --comp %s --gitcmt %s --create-newdir --config %s --branch %s --release-ver %s --current-ver %s' >& %s/%s-pdf.bld.log" % \
                    (blduser, bldhost, bldtool, sc, gitcmt, config, branch, release_ver, current_ver, log_dir, sc)
        
            print cmd
            # p = subprocess.Popen(cmd, 
            #                      stdout=subprocess.PIPE, 
            #                      stderr=subprocess.PIPE, shell=True)
            p = subprocess.Popen(cmd, shell=True)

            print "process id: ", p.pid
            # create the log
            # log[p.pid] = open("/tmp/%s.log" % p.pid, 'w')
            # if sc != "amas":
            #     build_processes.append(p)
            build_processes.append(p)

            
        while build_processes:
        
            time.sleep(1)          # check every sec
            for p in build_processes:
                if p.poll() is not None:
                    build_processes.remove(p)
                else:
                    time.sleep(1)          # check every sec
        
    master_comp = []
    for l in cfg['parallel_comp']:
        master_comp = master_comp + l
    if 'amas' in master_comp:
        print "copy build images to a central directory: %s" % cfg['rel_img_dir']
	open('nightly_build.log', 'a').close()
        amas_bldstatus = has_error(os.path.join(top_blddir, "install", "nightly_build.log"))
        if not amas_bldstatus:
            print "amas build successfully..."
            if os.getenv('COVERITY'):
                cmd = "%s --dir %s" %\
                    (os.path.join(cfg['coverity']['path'],
                                  cfg['coverity']['covanalyze']),
                     os.path.join(top_blddir, "install")
                     )
                print "running: ", cmd
                os.system(cmd)
            tag_build(cfg)
            record_last_build(cfg)
            record_keeping(cfg)
            update_qa_automation_file(cfg)
            gather_release_images(cfg)      
            #msu_generate(cfg)
            if branch == "R_4_2_0_BRANCH":
                iso_generate(cfg)
                msu_generate(cfg)
            # copy_img_download_path(cfg)
            rc = 0
        else:    
            print "amas failed to build..."
            rc = 1
    return rc       
        
if __name__ == "__main__":
    sys.exit(main())


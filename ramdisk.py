#!/usr/bin/env python
from __future__ import print_function, absolute_import, division

import logging

from collections import defaultdict
from errno import ENOENT
from errno import ENOSPC
from errno import ENOTEMPTY
from stat import S_IFDIR, S_IFLNK, S_IFREG
from sys import argv, exit
from time import time
import os
import pickle

from fuse import FUSE, FuseOSError, Operations

if not hasattr(__builtins__, 'bytes'):
    bytes = str

MAX_SIZE = 0
ALLOCATED_MEMORY = 0
IMAGE = None
files_ = None
data_=None
fd_=None
argc = 0
FILE_EMPTY = None
abspath = None

class Ramdisk(Operations):
    
    def persistFS(self):
        global argc, files_, data_, fd_, IMAGE, FP, abspath
        if argc==4:
            totalData = [files_, data_, fd_]
            pickle.dump(totalData, open(abspath, 'wb'))
    	return
            
    def __init__(self, image=None):
        global files_, data_, fd_, FILE_EMPTY, FP
        if((not image) or (image and FILE_EMPTY)):
            self.dictionary = {}
            self.data = defaultdict(bytes)
            self.fd = 0
            present = time()
            self.dictionary['/'] = dict(st_mode=(S_IFDIR | 0o755), st_ctime=present,
                                   st_mtime=present, st_atime=present, st_nlink=2)
            files_ = self.dictionary
            data_=self.data
            fd_=self.fd


        else:
            listOfData = pickle.load(open(image, 'rb'))
            self.dictionary = listOfData[0]
            self.data = listOfData[1]
            self.fd = listOfData[2]
            present = time()
            files_ = self.dictionary
            data_=self.data
            fd_=self.fd
    
    def viewDict(self):
        for a in self.dictionary:
            print (a, " : ", self.dictionary[a])

    def create(self, path, mode):
        global files_, data_, fd_
        self.dictionary[path] = dict(st_mode=(S_IFREG | mode), st_nlink=1,
                                st_size=0, st_ctime=time(), st_mtime=time(),
                                st_atime=time())

        self.fd += 1
        files_ = self.dictionary
        data_=self.data
        fd_=self.fd
        return self.fd

    def getattr(self, path, fh=None):
        if path not in self.dictionary:
            raise FuseOSError(ENOENT)
        return self.dictionary[path]

    def mkdir(self, path, mode):
        global files_, data_, fd_
        self.dictionary[path] = dict(st_mode=(S_IFDIR | mode), st_nlink=2,
                                st_size=0, st_ctime=time(), st_mtime=time(),
                                st_atime=time())

        self.dictionary['/']['st_nlink'] += 1

        files_ = self.dictionary
        data_=self.data
        fd_=self.fd
            

    def open(self, path, flags):
        global files_, data_, fd_
        self.fd += 1
        files_ = self.dictionary
        data_=self.data
        fd_=self.fd
        return self.fd


    def read(self, path, size, offset, fh):
        return self.data[path][offset:offset + size]

    def process_(self, string):
        i=0
        for a in string:
            if a=='/':
                return string[:i]
            i+=1
        return string

    def readdir(self, path, fh):
        readdirout = ['.', '..']
        for x in self.dictionary:
            if x.startswith(path) and x != path:
                if path=='/':
                    readdirout.append(self.process_(x[len(path):]))
                else:
                    readdirout.append(self.process_(x[len(path)+1:]))
        return set(readdirout)

    def readlink(self, path):#
        return self.data[path]
    

    def rename(self, old, new):
        global files_, data_, fd_
        self.dictionary[new] = self.dictionary.pop(old)
        files_ = self.dictionary
        data_=self.data
        fd_=self.fd

    def rmdir(self, path):
        global files_, data_, fd_
        for x in self.dictionary:
            if x.startswith(path) and x!=path:
		raise FuseOSError(ENOTEMPTY)
                return
        self.dictionary.pop(path)
        self.dictionary['/']['st_nlink'] -= 1
        files_ = self.dictionary
        data_=self.data
        fd_=self.fd
    

    def truncate(self, path, length, fh=None):
        global files_, data_, fd_
        global ALLOCATED_MEMORY, MAX_SIZE
        ALLOCATED_MEMORY-=len(self.data[path])
        ALLOCATED_MEMORY+=length
        self.data[path] = self.data[path][:length]
        self.dictionary[path]['st_size'] = length
        files_ = self.dictionary
        data_=self.data
        fd_=self.fd

    def unlink(self, path):
        global files_, data_, fd_
        global ALLOCATED_MEMORY, MAX_SIZE
        ALLOCATED_MEMORY-=len(self.data[path])
        self.dictionary.pop(path)
        files_ = self.dictionary
        data_=self.data
        fd_=self.fd

    def utimens(self, path, times=None):
        global files_, data_, fd_
        present = time()
        atime, mtime = times if times else (present, present)
        self.dictionary[path]['st_atime'] = atime
        self.dictionary[path]['st_mtime'] = mtime
        files_ = self.dictionary
        data_=self.data
        fd_=self.fd

    def write(self, path, data, offset, fh):
        global files_, data_, fd_
        global ALLOCATED_MEMORY, MAX_SIZE
        newlyAllocated = len(data)-len(self.data[path][offset:])
        if ALLOCATED_MEMORY + newlyAllocated > MAX_SIZE:
            raise FuseOSError(ENOSPC)
            return 0
        else:
            self.data[path] = self.data[path][:offset] + data
            self.dictionary[path]['st_size'] = len(self.data[path])
            ALLOCATED_MEMORY+=newlyAllocated
            files_ = self.dictionary
            data_=self.data
            fd_=self.fd
            return len(data)

    def destroy(self, path):
        self.persistFS()

if __name__ == '__main__':

    argc = len(argv)
    if argc==3:
        MAX_SIZE = int(argv[2])*1024*1024
        Mountpoint = argv[1]
        fuse = FUSE(Ramdisk(), Mountpoint, foreground=False)
    elif argc==4:
        MAX_SIZE = int(argv[2])*1024*1024
        Mountpoint = argv[1]
        IMAGE = argv[3]
        if not os.path.isfile(IMAGE):
            open(IMAGE, 'wb')
        if os.stat(IMAGE).st_size == 0:
            FILE_EMPTY = True
        else:
            FILE_EMPTY = False
        abspath = os.path.abspath(IMAGE)
        fuse = FUSE(Ramdisk(IMAGE), Mountpoint, foreground=False)
    else:
        print('usage : ')
        print('%s <mountpoint> <size>' % argv[0])
        print('or')
        print('%s <mountpoint> <size> <file>' % argv[0])
        exit(1)




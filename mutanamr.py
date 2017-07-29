import sys
import os
import time
import re

from PyQt5.QtWidgets import (QComboBox,QApplication,QWidget,QPushButton,QToolTip,QLineEdit,QListWidget,QMenuBar,QMenu,QTableWidget,QTableView,QTableWidgetItem,QDialog,QAction,QRadioButton,QButtonGroup,QLabel,QTreeWidget,QTreeWidgetItem)
from PyQt5.QtGui import QIcon,QFont

import mutagen
import mutagen.mp4
import mutagen.oggopus
import mutagen.oggvorbis
import pylast

artist_tags = {	'mp3': 'TPE1',
		'm4a': '\xa9ART',
		'opus': 'ARTIST',
}
album_tags = {	'mp3': 'TALB',
		'm4a': '\xa9alb',
		'opus': 'ALBUM',
}
title_tags = {	'mp3': 'TIT2',
		'm4a': '\xa9nam',
		'opus': 'TITLE',
}
genre_tags = {	'mp3': 'TCON',
		'm4a': '\xa9gen',
		'opus': 'GENRE',
}
cover_tags = {	'mp3': 'APIC',
		'm4a': 'covr',
}
desc_tags = {	'mp3': 'TIT3',
		'm4a': 'desc',
		'opus': 'DESCRIPTION',
}
no_tags = {	'mp3': 'TRCK',
		'm4a': 'trkn',
		'opus': 'TRACKNUMBER',
}

chlist = {      'artist': artist_tags,
                'title': title_tags,
                'album': album_tags,
                'genre': genre_tags,
              #  'cover': cover_tags,  # no support for cover art at the moment...
                'desc': desc_tags,
                'no':   no_tags,
}

columns=['artist','title','album','genre','desc','no']
localcol=[]
filetypes=['mp3','m4a','opus','ogg']
global pylastnet
pylastnet=None
all_search_cache={}
default_opts={}
opts={}

#lastfm functions
def lalbum(n):
    try:
        return n.get_album().get_name()
    except:
        return ''
def lno(n):
    try:
        a=n.get_album().get_tracks().index(n.get_name())
        if a>-1:
            return str(a)
    except:
        a=-1
    return str(a)

pyparam={'artist': lambda n:n.get_artist().get_name(),
        'title': lambda n:n.get_name(),
        'album': lalbum,
        'cover': lambda n:n.get_album().get_cover_image(),
        'desc': lambda n:n.get_wiki_content(),
        'no': lno}

#overrides
class QRowTreeWidgetItem(QTreeWidgetItem):
    def __init__(self, ro,*args, **kwargs):
        QTreeWidgetItem.__init__(self,*args,**kwargs)
        self.row=ro
    def get_row(self):
        return self.row

class metadata_obj(object):
    fname=''
    suffix=''
    sel_method='auto'
    change=None
    row=0
    def __init__(self,ro,fn):
        super().__init__()
        self.data={}
        self.mask={}
        self.fname=fn
        self.row=ro
        self.suffix=fn.split('.')[-1]
        if self.suffix in filetypes:
            if self.suffix=='mp3':
                self.change=mutagen.File(fn)
            elif self.suffix=='m4a':
                self.change=mutagen.mp4.MP4(fn)
            elif self.suffix=='opus':
                self.change=mutagen.oggopus.OggOpus(fn)
            elif self.suffix=='ogg':
                self.change=mutagen.oggvorbis.OggVorbis(fn)
                self.suffix='opus'
        for i in chlist.keys():
            if chlist[i][self.suffix] in self.change:
                self.data[i]=self.change[chlist[i][self.suffix]]
            else:
                self.data[i]=''
    def reset(self):
        for i in list(self.mask.keys()):
            self.mask.pop(i)
    def change_val(self,d,v):
        if d in self.data:
            self.mask[d]=v
    def commit_change(self):
        for i in list(self.mask.keys()):
            self.change[chlist[i][self.suffix]]=self.mask[i]
            self.data[i]=self.mask[i]
            self.mask.pop(i)
    def set_method(self,meth):
        self.sel_method=meth
    def get_data(self):
        return self.data
    def get_ch(self):
        return self.change
    def get_fname(self):
        return self.fname
    def get_changed(self):
        return len(self.mask)>0
    def get_mask(self):
        return self.mask
    def get_mask_pos(self):
        tmp=[]
        for i in self.mask:
            tmp.append(columns.index(i))
        return tmp
    def get_row(self):
        return self.row
    def get_method(self):
        return self.sel_method

def py_last_commit(mobj,query=None,sel_pos=0,reg='(?:-)[\w-]+[.][\w]+',delay=1):
    if type(query)!=type(None) and len(query)>0:
        item=None
        keyz=mobj.get_fname()
        if keyz not in all_search_cache:
            print('kk')
            item=change_lastfm_results(mobj,pylastnet,query)
        print(mobj.get_mask())
        if type(item)!=type(None):
            item=all_search_cache[keyz][0][all_search_cache[keyz][2]]
            if len(item)>0:
                item=item[sel_pos]
                for i in columns:
                    if i not in mobj.get_mask() and i in pyparam:
                        print(i)
                        mobj.change_val(i,pyparam[i](item))
                print(mobj.get_mask())
            time.sleep(delay)
            #all_search_cache.pop(mobj)

def auto_commit(mobj,query,sel_pos=0,reg={'title':"(?:.*?[A-Za-z0-9.()' ]+){1}.*?([A-Za-z0-9. ]+)",'artist':"(?:.*?[A-Za-z0-9. ]+){0}.*?([A-Za-z0-9.' ]+)"},delay=0):
    for i in reg:
        wrd=''.join(re.search(reg[i],query).group(1))
        mobj.change_val(i,wrd)
    time.sleep(delay)
#methods of automatic metadata editing
methods={'none': lambda n:None,
        'fm': py_last_commit,
        'auto': auto_commit,
        'int': lambda mobj,ln:mobj.change_val(n.text())}
method_list=['none','auto','fm','int']
def change_lastfm_results(mobj,net,query,fwd=False,modquery='^([^()\/]+)[\w() -]*\-[\w]+\.(?:opus|m4a|ogg|mp3)'):
    lastcache=[[],None,0]
    trk=None
    if type(net)==type(None):
        return None
    if mobj.get_fname() in all_search_cache:
        lastcache=all_search_cache[mobj.get_fname()]
    if type(lastcache[1]) is type(None):
        try:
            dobj=pylast.TrackSearch("",re.search(modquery,query).group(1),net)
            lastcache[1]=dobj
            trk=dobj.get_next_page()
            lastcache[0].append(trk)
        except:
            return None
    elif fwd:
        lastcache[2]+=1
        if lastcache[2]+1>=len(lastcache[0]):
            trk=lastcache[1].get_next_page()
            lastcache[0].append(trk)
        else:
            trk=lastcache[0][lastcache[2]]
    else:
        if lastcache[2]>0:
            lastcache[2]-=1
        trk=lastcache[0][lastcache[2]]
    all_search_cache[mobj.get_fname()]=lastcache
    return trk
        
class mutanamer_main(QWidget):    
    file_list=[]
    fname_list=[]
    row_list=[]
    srch={}
    sel_row=0
    def __init__(self):
        super().__init__()
        self.initUI()
    def table_add(self,row):
        loc=self.fname_list[row][0]+'/'+self.fname_list[row][1]
        fc=metadata_obj(row,fn=loc)
        fname_col=QTableWidgetItem(self.fname_list[row][1])
        fname_col.setFlags(fname_col.flags()^2)
        self.list.setItem(row+1,1,fname_col)
        metainfo=fc.get_data()
        col=2
        for u in columns:
            data_col=QTableWidgetItem(metainfo[u])
            self.list.setItem(row+1,col,data_col)
            col+=1
        self.file_list.append(fc)
        cmb=QComboBox()
        cmb.addItems(method_list)
        cmb.setCurrentIndex(0)
        self.list.setCellWidget(row+1,0,cmb)
        self.row_list+=[[cmb,fname_col,fc]]
    def table_init(self):
        dirn='/home/scholar/Music/lofilist'
        column_count=10 #link to number of elements in list thing
        for i in os.listdir(dirn):
            if (dirn,i) not in self.fname_list:
                self.fname_list+=[(dirn,i)]
        row_count=len(self.fname_list)
        self.list.setColumnCount(column_count)
        self.list.setRowCount(row_count+1)
        for i in range(len(self.fname_list)):
            self.table_add(i)
        self.list.setGeometry(50,90,720,300)  
    def initUI(self):
        self.dialog=sign_in_dialog()
        #menu options
        menub=QMenuBar(self)
        opt_men=QMenu("Options",self)
        opt_men.addAction("RegEx Options")
        network_opt=QAction("Configure Network",self)
        opt_men.addAction('Configure Network',self.dialog.show_dialog)
        opt_men.addSeparator()
        opt_men.addAction("Preferences")
        menub.addMenu(opt_men)
        #buttons
        b=QPushButton('Commit',self)
        b.setToolTip('Save changes to the specified files')
        b.resize(b.sizeHint())
        b.move(50,60)
        b.clicked.connect(lambda: self.auto_mask(commit=True))

        b_fetch=QPushButton('Pull',self)
        b_fetch.setToolTip('Get values using the specified methods')
        b_fetch.resize(b_fetch.sizeHint())
        b_fetch.move(50+(b.sizeHint().width()+10)*1,60)
        b_fetch.clicked.connect(self.auto_mask)

        b_reset=QPushButton('Reset',self)
        b_reset.setToolTip('Resets all non committed values')
        b_reset.resize(b_reset.sizeHint())
        b_reset.move(50+(b.sizeHint().width()+10)*2,60)
        b_reset.clicked.connect(self.reset_value)

        b_sel_all=QPushButton('Select All',self)
        b_sel_all.resize(b_sel_all.sizeHint())
        b_sel_all.move(50+3*(b.sizeHint().width()+10),60)
        b_sel_all.clicked.connect(self.sel_all)

        b_sel_none=QPushButton('Select None',self)
        b_sel_none.resize(b_sel_none.sizeHint())
        b_sel_none.move(50+(b.sizeHint().width()+10)*4,60)
        b_sel_none.clicked.connect(self.sel_to)

        res_prev=QPushButton('<',self)
        res_prev.resize(res_prev.sizeHint())
        res_prev.move(780,60)
        res_prev.clicked.connect(lambda: self.get_results())

        res_next=QPushButton('>',self)
        res_next.resize(res_next.sizeHint())
        res_next.move(1080-res_next.sizeHint().width(),60)
        res_next.clicked.connect(lambda: self.get_results(f=True))

       #lastfm search results
        self.lastfmres=QTreeWidget(self)
        self.lastfmres.setHeaderLabels(['Result','Value'])
        self.lastfmres.setGeometry(780,90,300,300)
        self.lastfmres.itemClicked.connect(self.sel_res_row)
        #searchbar
        tb=QLineEdit(self)
        tb.move(50,20)
        tb.resize(1030,35)
        #list of mutagen items
        self.list=QTableWidget(self)
        self.table_init()
        self.list.cellClicked.connect(self.sel_tbl_row)

        for i in range(len(chlist)+2):
            it=QTableWidgetItem((['action','fname']+columns)[i])
            it.setFlags(it.flags()^2)
            self.list.setItem(0,i,it)
        
        self.setGeometry(300,300,1130,640)
        self.setWindowTitle('mutanamr a0')
        self.show()
    def auto_mask(self,commit=False):
        for i in range(len(self.row_list)):
            target=self.row_list[i][2]
            print(self.row_list[10][2].get_mask())
            methods[target.get_method()](target,self.fname_list[i][1])
            if commit:
                target.commit_change()
                target.reset()
            self.update_value(target)
    def update_value(self,mobj):
        for u in mobj.get_mask_pos():
            item=QTableWidgetItem(mobj.get_mask()[columns[u]])
            self.list.setItem(mobj.get_row()+1,u+2,item)
    def reset_value(self):
        for i in self.file_list:
            for u in i.get_mask_pos():
                item=QTableWidgetItem(i.get_data()[columns[u]])
                self.list.setItem(i.get_row()+1,u+2,item)
            i.reset()
    def get_results(self,f=False): #put this in a separate thread to prevent gui freeze
        if self.sel_row>0:
            if type(pylastnet)!=type(None):
                t=change_lastfm_results(self.row_list[self.sel_row-1][2],pylastnet,self.fname_list[self.sel_row-1][1],fwd=f)
                self.lastfmres.clear()
                if len(t)==0:
                    tree_item=QTreeWidgetItem(['No results found',''])
                    self.lastfmres.addTopLevelItem(tree_item)
                for i in range(len(t)):
                    tree_item=QRowTreeWidgetItem(i,[t[i].get_artist().get_name(), t[i].get_name()])
                    self.lastfmres.addTopLevelItem(tree_item)
                self.no_results=len(t)
            else:
                tree_item=QTreeWidgetItem(["You're not signed in on any network"])
                self.lastfmres.addTopLevelItem(tree_item)
    def sel_tbl_row(self):
        self.sel_row=self.list.currentRow()
    def sel_res_row(self):
        if self.no_results>0:
            self.srch[self.sel_row]=self.lastfmres.currentItem().get_row()
        print(self.srch)
    def sel_all(self):
        for i in self.row_list:
            i[0].setCurrentIndex((i[0].currentIndex()%(len(method_list)-1))+1)
            i[2].set_method(method_list[i[0].currentIndex()])
            print(method_list[i[0].currentIndex()])
    def sel_to(self,ind=0):
        for i in self.row_list:
            i[0].setCurrentIndex(ind)

class sign_in_dialog(QWidget):
    le_info=['spinachman420','1lost1gained!','fba0656e7cce6602a2ed1ca6968dd556','890255d00dc2441257bbc0e3e025634f']
    def __init__(self):
        super().__init__()
        llastfm=[]
        ln_nm=('Username','Password','API Key','Secret Key')
        self.network_dialog=QDialog(self)
        self.network_dialog.setGeometry(400,200,350,250)
        self.network_dialog.setWindowTitle('Sign into FM API Network')
        for i in range(4):
            lne=QLineEdit(self.network_dialog)
            lne.setGeometry(80,20+40*i,250,30)
            if i>0:
                lne.setEchoMode(QLineEdit.Password)
            lne.setText(self.le_info[i])
            lbl=QLabel(ln_nm[i],self.network_dialog)
            lbl.move(10,25+40*i)
            llastfm.append(lne)
        but=QPushButton('Sign In',self.network_dialog)
        but.setGeometry(80,180,but.sizeHint().width(),but.sizeHint().height())
        but.clicked.connect(lambda: self.sign_in([llastfm[0].text(),llastfm[1].text(),llastfm[2].text(),llastfm[3].text()]))
        acc_group=QButtonGroup(self.network_dialog)
        is_lastfm=QRadioButton('Last.FM',self.network_dialog)
        is_lastfm.move(but.sizeHint().width()+100,180)
        is_lastfm.toggle()
        is_librefm=QRadioButton('Libre.FM',self.network_dialog)
        is_librefm.move(but.sizeHint().width()+180,180)
        acc_group.addButton(is_lastfm)
        acc_group.addButton(is_librefm)
    def show_dialog(self):
        self.network_dialog.exec_()
    def sign_in(self,argl):
        self.le_info=argl
        global pylastnet
        errorlabel=''
        try: 
            pylastnet=pylast.LastFMNetwork(username=argl[0],password_hash=pylast.md5(argl[1]),api_key=argl[2],api_secret=argl[3])
        except pylast.WSError:
            errorlbl=QLabel('Sign in failed. Check creditentials.',self.network_dialog)
        if type(pylastnet)!=type(None):
            errorlbl=QLabel('Signed in!',self.network_dialog)
        else:
            errorlbl=QLabel('Sign in failed, account error.',self.network_dialog)
        errorlbl.move(80,215)
        QLabel.show(errorlbl)

if __name__ == '__main__':
    app=QApplication(sys.argv)
    w=mutanamer_main()
    sys.exit(app.exec_())

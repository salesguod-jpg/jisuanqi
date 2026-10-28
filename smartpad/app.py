import sys
import csv
from pathlib import Path
from decimal import localcontext
from PySide6.QtCore import Qt, QTimer, QStandardPaths, QSettings
from PySide6.QtGui import QAction, QFont, QTextCursor
from PySide6.QtWidgets import (QApplication,QMainWindow,QPlainTextEdit,QWidget,QHBoxLayout,QMenu,QFileDialog,QMessageBox,QInputDialog,QFontDialog)
from .engine import format_number
from .recognition import analyze
from .storage import save,load,fingerprint

class Editor(QPlainTextEdit):
    composing=False
    def inputMethodEvent(self,event):
        self.composing=bool(event.preeditString())
        super().inputMethodEvent(event)
        if not self.composing: self.textChanged.emit()

class ResultPane(QWidget):
    def __init__(self,window):
        super().__init__();self.window=window;self.setMinimumWidth(230)
    def paintEvent(self,event):
        from PySide6.QtGui import QPainter
        p=QPainter(self);p.fillRect(self.rect(),self.palette().alternateBase());p.setFont(self.window.editor.font())
        editor=self.window.editor;block=editor.firstVisibleBlock()
        while block.isValid():
            top=editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top()
            if top>self.height(): break
            i=block.blockNumber()
            if i<len(self.window.lines):
                line=self.window.lines[i];label=self.window.label(line)
                p.setPen(self.palette().text().color())
                p.drawText(10,int(top),self.width()-15,int(editor.blockBoundingRect(block).height()),Qt.AlignTop|Qt.AlignLeft,label)
            block=block.next()
    def mousePressEvent(self,event):
        editor=self.window.editor;block=editor.firstVisibleBlock()
        while block.isValid():
            top=editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top()
            if top<=event.position().y()<top+editor.blockBoundingRect(block).height():
                editor.setTextCursor(QTextCursor(block));self.window.line_menu(event.globalPosition().toPoint());return
            block=block.next()

class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.resize(1100,750)
        self.preferences=QSettings('SmartCalculatorNotepad','SmartCalculatorNotepad')
        self.root=Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation));self.root.mkdir(parents=True,exist_ok=True)
        self.recovery=self.root/'recovery.scn';self.path=None;self.stamp=None;self.overrides={};self.previous_text='';self.lines=[];self.totals={};self.total=0
        self.option_actions={}
        self.options={'thousands':True,'autosave':True,'dark':False,'font':'Microsoft YaHei','size':12,'results':True}
        self.editor=Editor();self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.results=ResultPane(self);body=QWidget();layout=QHBoxLayout(body);layout.setContentsMargins(0,0,0,0);layout.addWidget(self.editor,7);layout.addWidget(self.results,3);self.setCentralWidget(body)
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(250);self.timer.timeout.connect(self.refresh)
        self.saver=QTimer(self);self.saver.setSingleShot(True);self.saver.setInterval(1200);self.saver.timeout.connect(self.autosave)
        self.editor.textChanged.connect(self.changed);self.editor.cursorPositionChanged.connect(self.status)
        self.editor.updateRequest.connect(lambda *_:self.results.update())
        self.editor.setContextMenuPolicy(Qt.CustomContextMenu);self.editor.customContextMenuRequested.connect(lambda pos:self.line_menu(self.editor.mapToGlobal(pos)))
        self.menus();self.restore();self.apply_style();self.refresh()
    def action(self,menu,title,callback,shortcut=None,check=None):
        action=QAction(title,self)
        if shortcut: action.setShortcut(shortcut)
        if check is not None: action.setCheckable(True);action.setChecked(check)
        action.triggered.connect(callback);menu.addAction(action);return action
    def menus(self):
        menu=self.menuBar().addMenu('文件')
        for title,method,key in [('新建',self.new,'Ctrl+N'),('打开',self.open,'Ctrl+O'),('保存',self.manual_save,'Ctrl+S'),('另存为',self.save_as,'Ctrl+Shift+S'),('导出原文 TXT',lambda:self.export('txt'),None),('导出附结果 TXT',lambda:self.export('results'),None),('导出 CSV',lambda:self.export('csv'),None)]: self.action(menu,title,method,key)
        recent=menu.addMenu('最近文件');recent.aboutToShow.connect(lambda:self.recent_menu(recent))
        menu=self.menuBar().addMenu('编辑')
        for title,method,key in [('撤销',self.editor.undo,'Ctrl+Z'),('重做',self.editor.redo,'Ctrl+Y'),('剪切',self.editor.cut,'Ctrl+X'),('复制',self.editor.copy,'Ctrl+C'),('粘贴',self.editor.paste,'Ctrl+V'),('全选',self.editor.selectAll,'Ctrl+A'),('搜索',self.search,'Ctrl+F'),('放大字体',lambda:self.zoom(1),'Ctrl++'),('缩小字体',lambda:self.zoom(-1),'Ctrl+-')]: self.action(menu,title,method,key)
        self.action(menu,'当前行规则…',lambda:self.line_menu(self.editor.mapToGlobal(self.editor.cursorRect().bottomRight())) )
        menu=self.menuBar().addMenu('设置')
        for title,key in [('自动保存','autosave'),('千分位','thousands'),('深色模式','dark'),('显示计算结果','results')]:
            self.option_actions[key]=self.action(menu,title,lambda enabled,k=key:self.set_option(k,enabled),check=self.options[key])
        self.action(menu,'字体…',self.choose_font)
    def set_option(self,key,value):
        self.options[key]=value;self.apply_style();self.changed()
    def apply_style(self):
        for key,action in self.option_actions.items():
            action.setChecked(bool(self.options[key]))
        self.editor.setFont(QFont(self.options.get('font','Microsoft YaHei'),int(self.options.get('size',12))))
        self.results.setVisible(bool(self.options.get('results',True)))
        self.setStyleSheet('QWidget {background:#20242c;color:#e7e9ee;} QMenu::item:selected {background:#44546d;} QPlainTextEdit {selection-background-color:#48699b;}' if self.options.get('dark') else '')
        self.results.update()
    def choose_font(self):
        ok,font=QFontDialog.getFont(self.editor.font(),self)
        if ok: self.options.update(font=font.family(),size=font.pointSize());self.apply_style();self.changed()
    def zoom(self,delta):
        self.options['size']=max(8,min(36,self.options['size']+delta));self.apply_style();self.changed()
    def changed(self):
        if self.editor.composing:return
        self.remap_rules();self.timer.start();self.saver.start();self.statusBar().showMessage('已修改，等待保存')
    def remap_rules(self):
        from difflib import SequenceMatcher
        current=self.editor.toPlainText()
        before=self.previous_text.split('\n');after=current.split('\n');mapped={}
        for tag,a,b,c,d in SequenceMatcher(None,before,after,autojunk=False).get_opcodes():
            if tag=='equal' or (tag=='replace' and b-a==d-c):
                for old,new in zip(range(a,b),range(c,d)):
                    if str(old) in self.overrides:mapped[str(new)]=self.overrides[str(old)]
        self.overrides=mapped;self.previous_text=current
    def refresh(self):
        if self.editor.composing:return
        self.lines,self.totals,self.total=analyze(self.editor.toPlainText(),self.overrides);self.results.update();self.status()
    def label(self,line):
        if line.value is not None:
            with localcontext() as ctx:
                ctx.prec=170
                value=line.value*100 if line.kind=='percent' else line.value
            return ('' if line.included else '○ ')+format_number(value,self.options['thousands'])+('%' if line.kind=='percent' else '')
        if line.kind=='heading':return '小计 '+format_number(self.totals.get(line.group,0),self.options['thousands'])
        if line.kind=='summary':return '汇总行（不计入）'
        return {'error':'错误：','pending':'待确认：'}.get(line.kind,'')+ (line.reason if line.kind in ('error','pending') else '')
    def status(self):
        index=self.editor.textCursor().blockNumber();group=self.lines[index].group if index<len(self.lines) else '未分组'
        self.setWindowTitle((self.path.name if self.path else '未命名')+' — 智能计算记事本')
        self.statusBar().showMessage(f'合计 {format_number(self.total)} | 当前组 {format_number(self.totals.get(group,0))} | {self.path.name if self.path else "未命名"} | {getattr(self,"save_status","尚未保存")} | 错误 {sum(l.kind=="error" for l in self.lines)} / 待确认 {sum(l.kind=="pending" for l in self.lines)}')
    def line_menu(self,point):
        self.refresh();index=self.editor.textCursor().blockNumber();menu=self.editor.createStandardContextMenu();menu.addSeparator()
        if index<len(self.lines):
            line=self.lines[index];info=menu.addAction(f'来源：{line.source or "—"}；{line.reason}');info.setEnabled(False)
        for title,role in [('自动识别','auto'),('指定金额','amount'),('指定普通数字','number'),('指定百分比','percent'),('忽略本行','ignore')]:
            self.action(menu,title,lambda checked=False,r=role:self.override(index,{'role':r}))
        self.action(menu,'切换是否参与合计',lambda:self.override(index,{'include':not self.lines[index].included}))
        self.action(menu,'指定本行算式…',lambda:self.expression(index))
        menu.exec(point)
    def override(self,index,change):
        if change.get('role')=='auto':self.overrides.pop(str(index),None)
        else:self.overrides.setdefault(str(index),{}).update(change)
        self.refresh();self.changed()
    def expression(self,index):
        value,ok=QInputDialog.getText(self,'手动修正','指定整行的计算算式（原文不变）：')
        if ok:self.override(index,{'expression':value})
    def document(self):return {'version':1,'text':self.editor.toPlainText(),'overrides':self.overrides,'settings':self.options,'path':str(self.path) if self.path else None,'stamp':self.stamp}
    def error(self,exc):
        self.save_status='保存或读取失败';self.status();QMessageBox.warning(self,'操作失败',str(exc))
    def autosave(self):
        if self.editor.composing:self.saver.start();return
        if not self.options['autosave']:return
        try:
            if self.path:self.stamp=save(self.path,self.document(),self.stamp)
            save(self.recovery,self.document())
            self.save_status='自动保存完成（含恢复副本）';self.status()
        except (OSError,ValueError) as exc:self.error(exc)
    def manual_save(self):
        if not self.path:return self.save_as()
        try:
            self.stamp=save(self.path,self.document(),self.stamp);save(self.recovery,self.document());self.save_status='已保存';self.remember();self.status();return True
        except (OSError,ValueError) as exc:self.error(exc);return False
    def save_as(self):
        path,_=QFileDialog.getSaveFileName(self,'另存为','','智能计算记事本 (*.scn)')
        if not path:return False
        old,stamp=self.path,self.stamp;self.path=Path(path);self.stamp=fingerprint(path)
        if self.manual_save():return True
        self.path,self.stamp=old,stamp;return False
    def checkpoint(self):
        if not self.editor.toPlainText() and not self.path:return True
        answer=QMessageBox.question(self,'切换文档','先保存当前文档？',QMessageBox.Save|QMessageBox.Discard|QMessageBox.Cancel,QMessageBox.Save)
        if answer==QMessageBox.Cancel:return False
        return self.manual_save() if answer==QMessageBox.Save else True
    def new(self):
        if not self.checkpoint():return
        self.saver.stop();self.path=None;self.stamp=None;self.overrides={};self.editor.clear();self.refresh()
    def open(self):
        path,_=QFileDialog.getOpenFileName(self,'打开','','记事本 (*.scn *.txt);;所有文件 (*)')
        if path:self.open_path(path)
    def open_path(self,path):
        if not self.checkpoint():return
        try:
            p=Path(path)
            data=load(p) if p.suffix.lower()=='.scn' else {'text':p.read_text(encoding='utf-8-sig'),'overrides':{}}
            self.saver.stop();self.path=p if p.suffix.lower()=='.scn' else None;self.stamp=fingerprint(p) if self.path else None
            self.apply_document(data);self.remember()
        except (OSError,ValueError) as exc:self.error(exc)
    def apply_document(self,data):
        self.overrides=data.get('overrides',{});self.options.update({k:v for k,v in data.get('settings',{}).items() if k!='mode'});self.editor.blockSignals(True);self.editor.setPlainText(data['text']);self.previous_text=data['text'];self.editor.blockSignals(False);self.apply_style();self.refresh()
    def remember(self):
        if not self.path:return
        recent=self.preferences.value('recent',[],type=list);recent=[str(self.path)]+[p for p in recent if p!=str(self.path)];self.preferences.setValue('recent',recent[:10]);self.preferences.setValue('last',str(self.path))
    def recent_menu(self,menu):
        menu.clear()
        for path in self.preferences.value('recent',[],type=list):self.action(menu,path,lambda checked=False,p=path:self.open_path(p))
    def restore(self):
        geometry=self.preferences.value('geometry')
        if geometry:self.restoreGeometry(geometry)
        try:
            if self.recovery.exists():
                data=load(self.recovery)
                if QMessageBox.question(self,'恢复文档','发现上次会话副本，是否恢复？')==QMessageBox.Yes:
                    self.path=Path(data['path']) if data.get('path') else None;self.stamp=data.get('stamp');self.apply_document(data);return
            last=self.preferences.value('last','')
            if last and Path(last).exists():self.path=Path(last);self.stamp=fingerprint(last);self.apply_document(load(last))
        except (OSError,ValueError) as exc:self.error(exc)
    def export(self,kind):
        path,_=QFileDialog.getSaveFileName(self,'导出','', 'CSV (*.csv)' if kind=='csv' else '文本 (*.txt)')
        if not path:return
        self.refresh()
        try:
            with open(path,'w',encoding='utf-8-sig' if kind=='csv' else 'utf-8',newline='') as stream:
                if kind=='csv':
                    writer=csv.writer(stream);writer.writerow(['原文','结果','来源','说明','参与合计','分组'])
                    for text,line in zip(self.editor.toPlainText().split('\n'),self.lines):writer.writerow([("'"+text) if text.startswith(('=','+','-','@')) else text,self.label(line),line.source,line.reason,line.included,line.group])
                elif kind=='txt':stream.write(self.editor.toPlainText())
                else:
                    stream.write('\n'.join(text+'\t'+self.label(line) for text,line in zip(self.editor.toPlainText().split('\n'),self.lines)))
                    stream.write('\n合计：'+format_number(self.total))
        except OSError as exc:self.error(exc)
    def search(self):
        text,ok=QInputDialog.getText(self,'搜索','查找文字：')
        if ok and text:
            if not self.editor.find(text):self.editor.moveCursor(QTextCursor.Start);self.editor.find(text)
    def closeEvent(self,event):
        self.preferences.setValue('geometry',self.saveGeometry())
        if not self.options['autosave']:
            if not self.checkpoint():event.ignore();return
        else:
            try:
                if self.path:self.stamp=save(self.path,self.document(),self.stamp)
                save(self.recovery,self.document())
            except (OSError,ValueError) as exc:self.error(exc);event.ignore();return
        event.accept()

def main():
    app=QApplication(sys.argv);app.setApplicationName('SmartCalculatorNotepad');app.setStyle('Fusion')
    window=Window();window.show();return app.exec()

if __name__=='__main__':sys.exit(main())

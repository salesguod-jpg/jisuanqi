import sys
import csv
import re
from pathlib import Path
from decimal import localcontext
from PySide6.QtCore import Qt, QTimer, QStandardPaths, QSettings, QPoint
from PySide6.QtGui import QAction, QFont, QTextCursor, QColor, QTextCharFormat, QSyntaxHighlighter
from PySide6.QtWidgets import (QApplication,QMainWindow,QPlainTextEdit,QWidget,QHBoxLayout,QMenu,QFileDialog,QMessageBox,QInputDialog,QFontDialog,QVBoxLayout,QLabel,QPushButton,QFrame,QSplitter,QToolTip)
from .engine import format_number
from .theme import LIGHT, DARK, stylesheet
from .recognition import analyze, recognize
from .storage import save,load,fingerprint

class Editor(QPlainTextEdit):
    composing=False
    calculate_line = None
    def keyPressEvent(self,event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and not self.composing:
            modifiers=event.modifiers()
            if modifiers==Qt.NoModifier and self.calculate_line and self.calculate_line():
                return
        super().keyPressEvent(event)
    def inputMethodEvent(self,event):
        self.composing=bool(event.preeditString())
        super().inputMethodEvent(event)
        if not self.composing: self.textChanged.emit()

class ResultPane(QWidget):
    def __init__(self,window):
        super().__init__();self.window=window;self.setMinimumWidth(250)
        self.setMouseTracking(True)
        self.setToolTip('点击行结果，查看来源或修改识别规则')
    def visible_blocks(self):
        editor=self.window.editor;block=editor.firstVisibleBlock()
        while block.isValid():
            # Editor and result pane have different local origins because of editor padding.
            top=editor.blockBoundingGeometry(block).translated(editor.contentOffset()).top()
            top+=editor.viewport().mapTo(self.window.paper,QPoint(0,0)).y()-self.mapTo(self.window.paper,QPoint(0,0)).y()
            if top>self.height():break
            yield block,top,int(editor.blockBoundingRect(block).height())
            block=block.next()
    def paintEvent(self,event):
        from PySide6.QtGui import QPainter
        p=QPainter(self);c=self.window.colors
        p.fillRect(self.rect(),QColor(c['surface']))
        p.setPen(QColor(c['border']));p.drawLine(0,0,0,self.height())
        for block,top,height in self.visible_blocks():
            i=block.blockNumber()
            if i>=len(self.window.lines):continue
            line=self.window.lines[i];label=self.window.label(line)
            if not label:continue
            is_number=line.value is not None
            font=QFont(self.window.editor.font())
            if not is_number:font.setPointSize(11);font.setBold(False)
            p.setFont(font)
            color=c['error'] if line.kind=='error' else c['warning'] if line.kind=='pending' else c['accent'] if is_number and line.included else c['muted']
            p.setPen(QColor(color))
            width=self.width()-40
            text=p.fontMetrics().elidedText(label,Qt.ElideRight,width)
            p.drawText(20,int(top),width,height,Qt.AlignTop|Qt.AlignLeft,text)
    def line_at(self,y):
        for block,top,height in self.visible_blocks():
            if top<=y<top+height:return block
    def mouseMoveEvent(self,event):
        block=self.line_at(event.position().y())
        if block and block.blockNumber()<len(self.window.lines):
            line=self.window.lines[block.blockNumber()]
            self.setToolTip(self.window.label(line)+'\n来源：'+(line.source or '—')+'\n'+line.reason)
        else:self.setToolTip('')
    def mousePressEvent(self,event):
        block=self.line_at(event.position().y())
        if block:
            self.window.editor.setTextCursor(QTextCursor(block));self.window.line_menu(event.globalPosition().toPoint())

class NoteHighlighter(QSyntaxHighlighter):
    def __init__(self,editor,window):
        super().__init__(editor.document());self.window=window
    def highlightBlock(self,text):
        if re.fullmatch(r'\s*(?:【.+】|#{1,6}\s+.+)\s*',text):
            style=QTextCharFormat();style.setForeground(QColor(self.window.colors['accent']));style.setFontWeight(QFont.Bold)
            self.setFormat(0,len(text),style)

class Window(QMainWindow):
    def __init__(self):
        super().__init__();self.resize(1280,850);self.setMinimumSize(860,560)
        self.preferences=QSettings('SmartCalculatorNotepad','SmartCalculatorNotepad')
        self.root=Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation));self.root.mkdir(parents=True,exist_ok=True)
        self.recovery=self.root/'recovery.scn';self.path=None;self.stamp=None;self.overrides={};self.previous_text='';self.lines=[];self.totals={};self.total=0
        self.option_actions={}
        self.options={'thousands':True,'autosave':True,'dark':False,'font':'Microsoft YaHei','size':24,'results':True,'enter_result':True}
        self.editor=Editor();self.editor.setLineWrapMode(QPlainTextEdit.NoWrap)
        self.colors=LIGHT
        self.build_workspace()
        self.highlighter=NoteHighlighter(self.editor,self)
        self.editor.calculate_line=self.append_result
        self.timer=QTimer(self);self.timer.setSingleShot(True);self.timer.setInterval(250);self.timer.timeout.connect(self.refresh)
        self.saver=QTimer(self);self.saver.setSingleShot(True);self.saver.setInterval(1200);self.saver.timeout.connect(self.autosave)
        self.editor.textChanged.connect(self.changed);self.editor.cursorPositionChanged.connect(self.status)
        self.editor.updateRequest.connect(lambda *_:self.results.update())
        self.editor.setContextMenuPolicy(Qt.CustomContextMenu);self.editor.customContextMenuRequested.connect(lambda pos:self.line_menu(self.editor.mapToGlobal(pos)))
        self.menus();self.restore();self.apply_style();self.refresh()
        QTimer.singleShot(100,self.editor.setFocus)
    def build_workspace(self):
        body=QWidget();body.setObjectName('workspace');outer=QVBoxLayout(body)
        outer.setContentsMargins(30,22,30,8);outer.setSpacing(18)
        header=QHBoxLayout();brand=QVBoxLayout();brand.setSpacing(5)
        title=QLabel('智能计算记事本');title.setObjectName('brand');brand.addWidget(title)
        subtitle=QLabel('自由记录，清晰算账。');subtitle.setObjectName('subtitle');brand.addWidget(subtitle)
        header.addLayout(brand);header.addStretch()
        self.save_badge=QLabel('本地离线');self.save_badge.setObjectName('saveBadge');header.addWidget(self.save_badge)
        for text,callback in [('打开',self.open),('保存',self.manual_save)]:
            button=QPushButton(text);button.clicked.connect(callback)
            if text=='保存':button.setObjectName('primary')
            header.addWidget(button)
        outer.addLayout(header)
        self.paper=QFrame();self.paper.setObjectName('paper');paperlayout=QVBoxLayout(self.paper);paperlayout.setContentsMargins(1,1,1,14);paperlayout.setSpacing(0)
        paperhead=QFrame();paperhead.setObjectName('paperHeader');head=QHBoxLayout(paperhead);head.setContentsMargins(26,14,20,14)
        self.document_label=QLabel('未命名笔记');self.document_label.setObjectName('section');head.addWidget(self.document_label);head.addStretch()
        for text,callback in [('A−',lambda:self.zoom(-2)),('A＋',lambda:self.zoom(2))]:
            button=QPushButton(text);button.setFixedWidth(48);button.setToolTip('调整编辑和结果字号');button.clicked.connect(callback);head.addWidget(button)
        self.result_toggle=QPushButton('计算结果');self.result_toggle.setCheckable(True);self.result_toggle.setChecked(True)
        self.result_toggle.clicked.connect(lambda checked:self.set_option('results',checked));head.addWidget(self.result_toggle)
        paperlayout.addWidget(paperhead)
        self.results=ResultPane(self)
        self.splitter=QSplitter(Qt.Horizontal);self.splitter.setChildrenCollapsible(False);self.splitter.setHandleWidth(1)
        self.editor.setPlaceholderText('在这里写下数字、算式或备注…\n\n例如：采购 1,500+2,300\n运费 680\n500×(1+15%)')
        self.editor.document().setDocumentMargin(24)
        self.splitter.addWidget(self.editor);self.splitter.addWidget(self.results);self.splitter.setStretchFactor(0,7);self.splitter.setStretchFactor(1,3);self.splitter.setSizes([800,340])
        paperlayout.addWidget(self.splitter,1);outer.addWidget(self.paper,1)
        footer=QHBoxLayout();totalbox=QVBoxLayout();totalbox.setSpacing(2)
        title=QLabel('全文合计');title.setObjectName('section');totalbox.addWidget(title)
        self.total_label=QLabel('0');self.total_label.setObjectName('totalValue');totalbox.addWidget(self.total_label);footer.addLayout(totalbox)
        footer.addSpacing(36);groupbox=QVBoxLayout();groupbox.setSpacing(5)
        self.group_name=QLabel('当前分组 · 未分组');self.group_name.setObjectName('section');groupbox.addWidget(self.group_name)
        self.group_label=QLabel('0');self.group_label.setObjectName('groupValue');groupbox.addWidget(self.group_label);footer.addLayout(groupbox)
        footer.addStretch();helpbox=QVBoxLayout()
        self.input_hint=QLabel();self.input_hint.setObjectName('hint');helpbox.addWidget(self.input_hint)
        self.issue_label=QLabel('所有金额已核对');self.issue_label.setObjectName('hint');helpbox.addWidget(self.issue_label)
        footer.addLayout(helpbox);outer.addLayout(footer);self.setCentralWidget(body)
    def append_result(self):
        if not self.options.get('enter_result',True):return False
        cursor=self.editor.textCursor()
        if cursor.hasSelection() or not cursor.atBlockEnd():return False
        text=cursor.block().text();tail=text.rsplit('=',1)[-1]
        line=recognize(tail)
        if line.kind!='amount' or line.value is None or not re.search(r'[+*/×÷、]|\d\s*-',line.source):return False
        cursor.beginEditBlock();cursor.insertText('='+format_number(line.value,False));cursor.endEditBlock()
        self.editor.setTextCursor(cursor);self.refresh();return True
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
        for title,key in [('自动保存','autosave'),('千分位','thousands'),('深色模式','dark'),('显示计算结果','results'),('回车追加算式结果','enter_result')]:
            self.option_actions[key]=self.action(menu,title,lambda enabled,k=key:self.set_option(k,enabled),check=self.options[key])
        self.action(menu,'字体…',self.choose_font)
    def set_option(self,key,value):
        self.options[key]=value;self.apply_style();self.changed()
    def apply_style(self):
        for key,action in self.option_actions.items():
            action.setChecked(bool(self.options[key]))
        self.colors=DARK if self.options.get('dark') else LIGHT
        font=QFont(self.options.get('font','Microsoft YaHei'),int(self.options.get('size',24)))
        font.setWeight(QFont.DemiBold);self.editor.setFont(font)
        self.results.setVisible(bool(self.options.get('results',True)));self.result_toggle.setChecked(bool(self.options.get('results',True)))
        self.input_hint.setText('Enter 追加结果 · Shift+Enter 换行' if self.options.get('enter_result',True) else '实时计算 · 原文保持不变')
        self.setStyleSheet(stylesheet(self.colors));self.highlighter.rehighlight();self.results.update()
    def choose_font(self):
        ok,font=QFontDialog.getFont(self.editor.font(),self)
        if ok: self.options.update(font=font.family(),size=font.pointSize());self.apply_style();self.changed()
    def zoom(self,delta):
        self.options['size']=max(8,min(36,self.options['size']+delta));self.apply_style();self.changed()
    def changed(self):
        if self.editor.composing:return
        self.remap_rules();self.timer.start();self.saver.start();self.save_status='已修改，等待保存';self.save_badge.setText(self.save_status);self.statusBar().showMessage(self.save_status)
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
        if hasattr(self,'total_label'):
            self.total_label.setText(format_number(self.total,self.options['thousands']))
            self.group_label.setText(format_number(self.totals.get(group,0),self.options['thousands']))
            self.group_name.setText('当前分组 · '+group)
            self.document_label.setText(self.path.name if self.path else '未命名笔记')
            self.save_badge.setText(getattr(self,'save_status','本地离线 · 自动保存' if self.options['autosave'] else '本地离线 · 手动保存'))
            errors=sum(l.kind=='error' for l in self.lines);pending=sum(l.kind=='pending' for l in self.lines)
            self.issue_label.setText(f'{errors} 处错误 · {pending} 行待确认' if errors or pending else '无计算错误 · 百分号始终 ÷100')
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

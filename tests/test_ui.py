import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PySide6.QtWidgets import QApplication,QMessageBox
from PySide6.QtGui import QInputMethodEvent,QTextCursor
from PySide6.QtCore import QSettings
from smartpad.app import Window
from smartpad.storage import load

def test_editor_workflow(tmp_path,monkeypatch):
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path/'data'))
    monkeypatch.setenv('XDG_CONFIG_HOME',str(tmp_path/'config'))
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(Window,'restore',lambda self:None)
    window=Window();window.root=tmp_path;window.recovery=tmp_path/'recovery.scn'
    window.editor.setPlainText('采购 1500+2300\n运费 680\n手续费 120.5');window.refresh()
    assert window.total==4600.5
    window.override(1,{'include':False});assert window.total==3920.5
    cursor=window.editor.textCursor();cursor.movePosition(QTextCursor.Start);cursor.insertText('标题\n');window.refresh()
    assert window.overrides['2']['include'] is False
    assert window.total==3920.5
    window.path=tmp_path/'note.scn';window.stamp=None;window.autosave()
    assert load(window.path)['text']==window.editor.toPlainText()
    assert load(window.recovery)['overrides']==window.overrides
    before=window.editor.toPlainText();event=QInputMethodEvent('中文预编辑',[]);app.sendEvent(window.editor,event)
    assert window.editor.composing;window.refresh();assert window.editor.toPlainText()==before
    commit=QInputMethodEvent();commit.setCommitString('中文');app.sendEvent(window.editor,commit)
    assert not window.editor.composing;assert '中文' in window.editor.toPlainText()
    window.show();app.processEvents();assert window.results.isVisible()
    window.timer.stop();window.saver.stop();window.hide();window.deleteLater();app.processEvents()

def test_recovery_stamp(tmp_path,monkeypatch):
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path/'data'))
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(Window,'restore',lambda self:None)
    window=Window();window.recovery=tmp_path/'recovery.scn';window.path=tmp_path/'saved.scn'
    window.editor.setPlainText('100');window.refresh();window.autosave()
    data=load(window.recovery)
    from smartpad.storage import fingerprint
    assert data['stamp']==fingerprint(window.path)
    window.editor.setPlainText('200');window.refresh();window.autosave()
    assert load(window.path)['text']=='200'
    window.timer.stop();window.saver.stop();window.deleteLater();app.processEvents()

def test_standard_percent_ui_and_legacy_document(tmp_path,monkeypatch):
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path/'data'))
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(Window,'restore',lambda self:None)
    window=Window()
    window.apply_document({'text':'500+15%\n500-15%\n500×15%\n500÷15%\n500×(1+15%)\n100×0.5\n0.15','settings':{'mode':'calculator'}})
    assert 'mode' not in window.options
    assert 'mode' not in window.option_actions
    assert [window.label(line) for line in window.lines]==['500.15','499.85','75','3,333.3333','575','50','○ 15%']
    assert window.lines[-1].included is False
    window.timer.stop();window.saver.stop();window.deleteLater();app.processEvents()

def test_comfort_enter_and_appearance(tmp_path,monkeypatch):
    from PySide6.QtTest import QTest
    from PySide6.QtCore import Qt
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path/'data'))
    app=QApplication.instance() or QApplication([])
    monkeypatch.setattr(Window,'restore',lambda self:None)
    window=Window();window.editor.setPlainText('采购 1,500+2,300')
    window.editor.moveCursor(QTextCursor.End)
    QTest.keyClick(window.editor,Qt.Key_Return);window.refresh()
    assert window.editor.toPlainText()=='采购 1,500+2,300=3800'
    assert window.total==3800 and window.total_label.text()=='3,800'
    QTest.keyClick(window.editor,Qt.Key_Return)
    assert window.editor.toPlainText().endswith('\n')
    window.editor.setPlainText('500+15%');window.editor.moveCursor(QTextCursor.End)
    QTest.keyClick(window.editor,Qt.Key_Return)
    assert window.editor.toPlainText()=='500+15%=500.15'
    window.editor.undo();assert window.editor.toPlainText()=='500+15%'
    window.editor.setPlainText('100/3');window.editor.moveCursor(QTextCursor.End)
    QTest.keyClick(window.editor,Qt.Key_Return);window.refresh()
    assert str(window.lines[0].value).startswith('33.333333333')
    window.set_option('dark',True);assert window.colors['bg']=='#121A22'
    window.set_option('results',False);assert window.results.isHidden()
    window.set_option('enter_result',False)
    window.editor.setPlainText('500+15%');window.editor.moveCursor(QTextCursor.End)
    QTest.keyClick(window.editor,Qt.Key_Return);assert window.editor.toPlainText()=='500+15%\n'
    window.set_option('enter_result',True)
    window.editor.setPlainText('500+15%');window.editor.moveCursor(QTextCursor.End)
    QTest.keyClick(window.editor,Qt.Key_Return,Qt.ShiftModifier)
    assert window.editor.toPlainText()=='500+15%\n'
    window.timer.stop();window.saver.stop();window.deleteLater();app.processEvents()

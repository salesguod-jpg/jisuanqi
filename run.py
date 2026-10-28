import sys

def smoke_test():
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QTimer
    from smartpad.app import Window
    app=QApplication(sys.argv)
    # Isolated smoke test must not restore or overwrite a user's documents.
    Window.restore=lambda self:None
    Window.closeEvent=lambda self,event:event.accept()
    window=Window();window.options['autosave']=False
    window.editor.setPlainText('采购 1500+2300\n运费 680\n手续费 120.5')
    window.refresh()
    if str(window.total)!='4600.5':raise RuntimeError('计算器自检失败')
    window.show()
    QTimer.singleShot(200,app.quit)
    return app.exec()

if __name__ == '__main__':
    if '--smoke-test' in sys.argv:
        raise SystemExit(smoke_test())
    from smartpad.app import main
    raise SystemExit(main())

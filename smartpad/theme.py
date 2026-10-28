"""Shared desktop colors; no browser or web runtime required."""
LIGHT = dict(bg='#F3F5F7', surface='#FFFFFF', ink='#182738', muted='#66788A',
             border='#E2E8EE', accent='#167A62', soft='#EAF5F0', hover='#F0F4F7',
             error='#BD4D49', warning='#9B701D', selection='#C9EADC')
DARK = dict(bg='#121A22', surface='#1A2530', ink='#E3EBF2', muted='#9AACBC',
            border='#2C3B48', accent='#74D5B3', soft='#203F37', hover='#253543',
            error='#FF9A93', warning='#EAC57B', selection='#315D50')

def stylesheet(c):
    return f'''
    QMainWindow, QWidget#workspace {{ background: {c['bg']}; color: {c['ink']}; }}
    QWidget {{ color: {c['ink']}; }}
    QMenuBar {{ background: {c['surface']}; padding: 6px 20px; border-bottom: 1px solid {c['border']}; }}
    QMenuBar::item {{ padding: 5px 12px; border-radius: 5px; }}
    QMenuBar::item:selected, QMenu::item:selected {{ background: {c['soft']}; }}
    QMenu {{ background: {c['surface']}; border: 1px solid {c['border']}; padding: 6px; }}
    QMenu::item {{ padding: 8px 20px; }}
    QFrame#paper {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 16px; }}
    QFrame#paperHeader {{ background: transparent; border-bottom: 1px solid {c['border']}; }}
    QLabel {{ background: transparent; }}
    QLabel#brand {{ font-size: 23px; font-weight: 700; }}
    QLabel#subtitle, QLabel#hint {{ color: {c['muted']}; font-size: 12px; }}
    QLabel#section {{ font-size: 12px; color: {c['muted']}; font-weight: 600; }}
    QLabel#saveBadge {{ color: {c['accent']}; background: {c['soft']}; border-radius: 12px; padding: 6px 12px; font-size: 12px; }}
    QLabel#totalValue {{ font-size: 34px; color: {c['accent']}; font-weight: 700; }}
    QLabel#groupValue {{ font-size: 20px; font-weight: 600; }}
    QPlainTextEdit {{ background: {c['surface']}; color: {c['ink']}; border: none;
        selection-background-color: {c['selection']}; selection-color: {c['ink']}; padding: 12px 8px; }}
    QPushButton, QToolButton {{ background: {c['surface']}; border: 1px solid {c['border']}; border-radius: 8px; padding: 8px 16px; font-size: 13px; }}
    QPushButton:hover, QToolButton:hover {{ background: {c['hover']}; }}
    QPushButton#primary {{ background: {c['soft']}; color: {c['accent']}; border-color: {c['soft']}; font-weight: 600; }}
    QPushButton:checked {{ background: {c['soft']}; color: {c['accent']}; }}
    QStatusBar {{ background: {c['bg']}; color: {c['muted']}; border: none; font-size: 11px; }}
    QStatusBar::item {{ border: none; }}
    QScrollBar:vertical {{ background: {c['surface']}; width: 10px; margin: 0; }}
    QScrollBar::handle:vertical {{ background: {c['border']}; border-radius: 4px; min-height: 30px; }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
    QSplitter::handle {{ background: {c['border']}; }}
    QDialog {{ background: {c['surface']}; }}
    QLineEdit {{ background: {c['surface']}; border: 1px solid {c['border']}; padding: 8px; color: {c['ink']}; }}
    '''

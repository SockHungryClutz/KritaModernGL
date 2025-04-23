from krita import *
from PyQt5.QtCore import QSettings, QStandardPaths
# Import moderngl here

class ModernGL(Extension):
    def __init__(self, parent):
        super().__init__(parent)

    def setup(self):
        pass

    def ModernGLWindow(self):
        # Build the window here
        # Should have at least a editable text box and a button to make it go
        # Figure out how to hook into moderngl library
        # Then give the user string to the library to work magic
        # Stretch goals:
        #   * Add scrollable box for error output
        #   * Add support for vertex instead of pixel shaders
        #   * Add help for possible inputs
        pass

    def createActions(self, window):
        mainAction = window.createAction("KritaModernGL", "OpenGL Shader Programming")
        mainAction.triggered.connect(self.ModernGLWindow)

Krita.instance().addExtension(ModernGL(Krita.instance()))

from krita import *
from PyQt5.QtCore import Qt, QRect, QSettings, QStandardPaths
from PyQt5.QtWidgets import QDialog, QLabel, QDialogButtonBox, QVBoxLayout, QMessageBox
from zipfile import ZipFile
import logging
import platform
import sys
import os

# Dialog box
# TODO: Split this off into its own class/file for render shader
class MainDialog(QDialog):
    def __init__(self, extension, parent=None):
        super(MainDialog, self).__init__(parent)
        self.ext = extension
        
        #self.helpWindow = QMessageBox()
        # TODO: custom labelled buttons?
        self.buttonBox = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Close, self)
        self.setWindowModality(Qt.WindowModal)
        self.buttonBox.accepted.connect(self.applyChanges)
        # TODO: save window settings even when cancelled
        self.buttonBox.rejected.connect(self.reject)
        #self.buttonBox.helpRequested.connect(self.showHelp)
        
        self.vertLabel = QLabel("Vertex Shader:", self)
        self.vertBox = QTextEdit()
        self.vertBox.setAcceptRichText(False)
        self.vertBox.setTabChangesFocus(False)
        
        self.fragLabel = QLabel("Fragment Shader:", self)
        self.fragBox = QTextEdit()
        self.fragBox.setAcceptRichText(False)
        self.fragBox.setTabChangesFocus(False)
        
        self.errLabel = QLabel("Errors:", self)
        self.errBox = QTextEdit()
        self.errBox.setAcceptRichText(False)
        self.errBox.setReadOnly(True)
        self.errBox.setPlaceholderText("Enter shader code above and click OK, warnings and errors will appear here.")
        
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.vertLabel)
        vbox.addWidget(self.vertBox)
        vbox.addWidget(self.fragLabel)
        vbox.addWidget(self.fragBox)
        vbox.addWidget(self.errLabel)
        vbox.addWidget(self.errBox)
        vbox.addWidget(self.buttonBox)
        
        self.readSettings()
        
        self.setWindowTitle("OpenGL Shader Programming")
        self.setSizeGripEnabled(True)
        self.show()
        self.activateWindow()

    def applyChanges(self):
        doc = Krita.instance().activeDocument()
        if not doc:
            self.errBox.setPlainText("!ERROR!: You need to have a document open to use this script!")
            return
        # Get information for the buffer format
        # Number of components is the number of capitals in the color model, unless GRAYA
        doc = Krita.instance().activeDocument()
        node = doc.activeNode()
        colorModel = node.colorModel()
        if colorModel == "GRAYA":
            components = 2
        else:
            components = sum(1 for c in colorModel if c.isupper())
        colorDepth = node.colorDepth()
        colorDepth = colorDepth[0].lower() + str(int(colorDepth[1:]) // 8)
        # Create input texture from current layer
        inputTexture = self.ext.ctx.texture((doc.width(), doc.height()), components, data=node.projectionPixelData(0, 0, doc.width(), doc.height()), dtype=colorDepth)
        # Create output buffer with canvas size and color info
        outputTexture = self.ext.ctx.texture((doc.width(), doc.height()), components, dtype=colorDepth)
        outFrameBuffer = self.ext.ctx.framebuffer([outputTexture])
        # Create a shader program from the text boxes
        program = self.ext.ctx.program(
            vertex_shader=self.vertBox.toPlainText(),
            fragment_shader=self.fragBox.toPlainText(),
        )
        # Set the texture units for the textures
        outFrameBuffer.use() # Through magic, framebuffers are automatically used as output(?)
        # TODO: test if selected layer is ctually being piped in properly and useable
        inputTexture.use()
        # Hacky workaround, use the length of the first vec3 as the number of vertices
        # If you need to render more, add a comment like "vec3 vertices[LENGTH]"
        # TODO: Add a box where the user can put in however many vertices themselves
        vao = self.ext.ctx.vertex_array(program, [])
        vertShader = self.vertBox.toPlainText()
        try:
            vertices = int(vertShader[vertShader.find("[",vertShader.find("vec3"))+1:vertShader.find("]",vertShader.find("vec3"))])
            vao.vertices = vertices
        except ValueError as e:
            # Could not parse number of vertices, good luck
            pass
        self.ext.ctx.clear()
        # Display any errors in warningWidget
        try:
            vao.render()
            # Add new buffer to the canvas
            curNode = node.duplicate()
            curNode.setName("Render Result")
            curNode.setPixelData(outputTexture.read(), 0, 0, doc.width(), doc.height())
            node.parentNode().addChildNode(curNode, doc.activeNode())
            doc.refreshProjection()
        except Exception as e:
            self.errBox.setPlainText("!ERROR!: " + str(e))
        # Cleanup
        inputTexture.release()
        outputTexture.release()
        outFrameBuffer.release()
        vao.release()
        program.release()
        self.saveSettings()

    def closeEvent(self, event):
        self.saveSettings()
        event.accept()

    def saveSettings(self):
        rect = self.geometry()
        self.ext.settings.setValue("mgl_geometry", rect)
        if self.vertBox.toPlainText() != "":
            self.ext.settings.setValue("mgl_vert_shader", self.vertBox.toPlainText())
        if self.fragBox.toPlainText() != "":
            self.ext.settings.setValue("mgl_frag_shader", self.fragBox.toPlainText())
        self.ext.settings.sync()

    def readSettings(self):
        rect = self.ext.settings.value("mgl_geometry", QRect(200, 200, 800, 800))
        self.setGeometry(rect)
        self.vertBox.setPlainText(self.ext.settings.value("mgl_vert_shader", ""))
        self.fragBox.setPlainText(self.ext.settings.value("mgl_frag_shader", ""))

class KritaModernGL(Extension):
    def __init__(self, parent):
        super().__init__(parent)
        # Set up logger
        logging.basicConfig(filename = Krita.getAppDataLocation() + "/pykrita/kritamoderngl/log.log", level = logging.INFO)
        self.log = logging.getLogger(__name__)
        # ModernGL is compiled per platform per architecture per python version
        # Distribute with all packages, then only unpack the relevant ones
        # Determine the python version
        vers_tuple = platform.python_version_tuple()
        vers = vers_tuple[0] + vers_tuple[1]
        # Determine the platform
        plat = platform.system()
        if plat.lower() == "linux":
            # Assume manylinux will work
            # Linux users should be smart enough to change this if they use a different distro
            plat = "manylinux_2_17_x86_64.manylinux2014_x86_64"
        elif plat.lower() == "windows":
            plat = "win_amd64"
        elif plat.lower() == "darwin":
            # MacOS may be x86_64 or ARM64
            if platform.machine().lower() == "arm64":
                plat = "macosx_11_0_arm64"
            else:
                # Different platform is named depending on python version
                if int(vers_tuple[1]) >= 12:
                    plat = "macosx_10_13_x86_64"
                else:
                    plat = "macosx_10_9_x86_64"
        # Construct the expected file name
        mgl_name = "moderngl-5.12.0-cp" + vers + "-cp" + vers + "-" + plat
        glc_name = "glcontext-3.0.0-cp" + vers + "-cp" + vers + "-" + plat
        # If it is not a directory, extract the zip to a directory
        mgl_path = Krita.getAppDataLocation() + "/pykrita/kritamoderngl/bin/"
        if not os.path.exists(os.path.join(mgl_path, mgl_name)):
            os.makedirs(os.path.join(mgl_path, mgl_name))
            try:
                with ZipFile(os.path.join(mgl_path, mgl_name) + ".whl", "r") as mgl_zip:
                    mgl_zip.extractall(os.path.join(mgl_path, mgl_name))
            except:
                # This platform has no valid ModernGL build
                self.log.warning("No valid ModernGL build found, attempted: %s", mgl_name)
        # Repeat for glcontext
        if not os.path.exists(os.path.join(mgl_path, glc_name)):
            os.makedirs(os.path.join(mgl_path, glc_name))
            try:
                with ZipFile(os.path.join(mgl_path, glc_name) + ".whl", "r") as glc_zip:
                    glc_zip.extractall(os.path.join(mgl_path, glc_name))
            except:
                # This platform has no valid GLContext build
                self.log.warning("No valid GLContext build found, attempted: %s", glc_name)
        # Add the directory to the path
        sys.path.append(os.path.join(mgl_path, mgl_name))
        sys.path.append(os.path.join(mgl_path, glc_name))
        # Import the correct version of ModernGL
        try:
            import moderngl
            # Initialize ModernGL here to have a persistant context
            self.ctx = moderngl.create_context(standalone=True)
            self.log.info("ModernGL initialized, GL_VENDOR: %s, GL_RENDERER: %s, GL_VERSION: $s", self.ctx.info["GL_VENDOR"], self.ctx.info["GL_RENDERER"], self.ctx.info["GL_VERSION"])
        except ImportError as e:
            self.log.warning("Failed to import ModernGL: %s", str(e))

    def setup(self):
        pass

    def ModernGLWindow(self):
        # Build the window here
        # Should have at least a editable text box and a button to make it go
        # Figure out how to hook into moderngl library
        # Then give the user string to the library to work magic
        # Stretch goals:
        #   * Make the input boxes monospace
        #   * Add help for possible inputs
        configPath = QStandardPaths.writableLocation(QStandardPaths.GenericConfigLocation)
        self.settings = QSettings(configPath + '/krita-scripterrc', QSettings.IniFormat)
        self.mainDialog = MainDialog(self)

    def createActions(self, window):
        mainAction = window.createAction("KritaModernGL", "OpenGL Render Shader Programming")
        mainAction.triggered.connect(self.ModernGLWindow)
        # TODO: Make a second action, window, and class for Compute Shader Programming

Krita.instance().addExtension(KritaModernGL(Krita.instance()))

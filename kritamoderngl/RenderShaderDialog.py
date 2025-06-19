from krita import *
from PyQt5.QtCore import Qt, QRect, QSettings, QStandardPaths
from PyQt5.QtGui import QIntValidator, QFont
from PyQt5.QtWidgets import QDialog, QFileDialog, QLabel, QHBoxLayout, QVBoxLayout, QMessageBox, QLineEdit, QTextEdit
import logging

# Dialog box for render shader
class RenderShaderDialog(QDialog):
    def __init__(self, extension, parent=None):
        super(RenderShaderDialog, self).__init__(parent)
        self.ext = extension
        
        self.helpWindow = QMessageBox()
        self.buttonBox = QDialogButtonBox(
            QDialogButtonBox.Open |
            QDialogButtonBox.Save |
            QDialogButtonBox.Ok |
            QDialogButtonBox.Help |
            QDialogButtonBox.Cancel,
            self)
        self.buttonBox.button(QDialogButtonBox.Ok).setText("Run")
        self.buttonBox.button(QDialogButtonBox.Ok).clicked.connect(self.applyChanges)
        self.buttonBox.button(QDialogButtonBox.Open).clicked.connect(self.openFile)
        self.buttonBox.button(QDialogButtonBox.Save).clicked.connect(self.saveFile)
        self.buttonBox.helpRequested.connect(self.showHelp)
        self.buttonBox.rejected.connect(self.saveAndReject)
        self.setWindowModality(Qt.WindowModal)
        monoFont = QFont("Monospace")
        monoFont.setStyleHint(QFont.TypeWriter)
        
        self.vertLayout = QHBoxLayout()
        self.vertLabel = QLabel("Vertex Shader:", self)
        self.vertLabel2 = QLabel("Number of vertices to render:", self)
        self.vertNumber = QLineEdit("-1", self)
        self.vertNumber.setValidator(QIntValidator(-1, 2147483647, self))
        self.vertLayout.addWidget(self.vertLabel2)
        self.vertLayout.addWidget(self.vertNumber)
        self.vertBox = QTextEdit()
        self.vertBox.setAcceptRichText(False)
        self.vertBox.setTabChangesFocus(False)
        self.vertBox.setFont(monoFont)
        
        self.fragLabel = QLabel("Fragment Shader:", self)
        self.fragBox = QTextEdit()
        self.fragBox.setAcceptRichText(False)
        self.fragBox.setTabChangesFocus(False)
        self.fragBox.setFont(monoFont)
        
        self.errLabel = QLabel("Errors:", self)
        self.errBox = QTextEdit()
        self.errBox.setAcceptRichText(False)
        self.errBox.setReadOnly(True)
        self.errBox.setPlaceholderText("Enter shader code above and click Run, warnings and errors will appear here.")
        
        vbox = QVBoxLayout(self)
        vbox.addWidget(self.vertLabel)
        vbox.addLayout(self.vertLayout)
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
        
        # For some reason, the geometry as applied differs from how it should be
        # Save the difference and apply it on save
        self.geometryDelta = QRect(
            self.geometry().x() - self.readGeometry.x(),
            self.geometry().y() - self.readGeometry.y(),
            self.geometry().width() - self.readGeometry.width(),
            self.geometry().height() - self.readGeometry.height())

    def applyChanges(self):
        doc = Krita.instance().activeDocument()
        if not doc:
            self.errBox.setPlainText("You need to have a document open to use this script!")
            return
        newNode = None
        # Get information for the buffer format
        # Number of components is the number of capitals in the color model, unless GRAYA
        node = doc.activeNode()
        colorModel = node.colorModel()
        if colorModel == "GRAYA":
            components = 2
        else:
            components = sum(1 for c in colorModel if c.isupper())
        colorDepth = node.colorDepth()
        colorDepth = colorDepth[0].lower() + str(int(colorDepth[1:]) // 8)
        # Must specify this context otherwise Krita will cause issues if using OpenGL for main renderer
        with self.ext.ctx as ctx:
            ## Create input texture from current layer
            inputTexture = ctx.texture((doc.width(), doc.height()), components, data=node.projectionPixelData(0, 0, doc.width(), doc.height()), dtype=colorDepth)
            ## Create output buffer with canvas size and color info
            outputTexture = ctx.texture((doc.width(), doc.height()), components, dtype=colorDepth)
            outFrameBuffer = ctx.framebuffer([outputTexture])
            ## Create a shader program from the text boxes
            try:
                program = ctx.program(
                    vertex_shader=self.vertBox.toPlainText(),
                    fragment_shader=self.fragBox.toPlainText())
            except Exception as e:
                self.errBox.setPlainText(str(e))
                # Cleanup and early exit
                inputTexture.release()
                outputTexture.release()
                outFrameBuffer.release()
                self.saveSettings()
                return
            # Set the texture units for the textures
            outFrameBuffer.use() # Through magic, framebuffers are automatically used as output
            inputTexture.use() # And textures can be used as input with a sampler2D
            vao = ctx.vertex_array(program, [])
            try:
                vertices = int(self.vertNumber.text())
                if vertices != -1:
                    vao.vertices = vertices
            except ValueError as e:
                # Could not parse number of vertices, good luck
                pass
            
            ctx.clear()
            # Display any errors in warningWidget
            try:
                vao.render()
                ctx.finish()
                # Put the result into a new node
                newNode = doc.createNode("Render Result", "paintlayer")
                newNode.setPixelData(outputTexture.read(), 0, 0, doc.width(), doc.height())
            except Exception as e:
                self.errBox.setPlainText(str(e))
            # Cleanup
            inputTexture.release()
            outputTexture.release()
            outFrameBuffer.release()
            vao.release()
            program.release()
        if newNode:
            # Exit the context scope before adding a new node
            node.parentNode().addChildNode(newNode, node)
            doc.refreshProjection()
        self.saveSettings()

    def showHelp(self):
        self.helpWindow.setText("Krita ModernGL Render Shader Programming")
        self.helpWindow.setInformativeText("""This tool is designed for running GLSL vertex and fragment shaders inside of Krita and rendering their output to a new layer in the current document. If you would like to learn more, https://learnopengl.com has good tutorials. Here are some more useful bits of info:

   > No vertices are fed into the vertex shader from the program, you will need to define your own vertices inside the shader to render.
   > Use the text box above the vertex shader to specify how many vertices are to be processed.
   > The render primitive mode is triangles since this is the default.
   > Varyings output from the vertex shader can be used as inputs to the fragment shader.
   > The output of the fragment shader will be rendered to a new layer added above the current selected layer.
   > The current selected layer can be used as a texture input with uniform sampler2D.
   > There is no syntax highlighting, it is advisable you use some other editor to make the shaders.""")
        self.helpWindow.exec()

    def openFile(self):
        # Open a file selection dialog
        files = QFileDialog.getOpenFileNames(
            self,
            "Select one or more files to open",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "Shaders (*.vert *.frag)")
        vertexFile = None
        fragmentFile = None
        multipleVert = False
        multipleFrag = False
        # Iterate over all selected files
        for file in files[0]:
            ext =  file.rsplit(".", 1)[1]
            # Take the first .vert and .frag files listed
            if ext.lower() == "vert":
                if vertexFile:
                    multipleVert = True
                else:
                    vertexFile = file
            elif ext.lower() == "frag":
                if fragmentFile:
                    multipleFrag = True
                else:
                    fragmentFile = file
        # If multiple files of a specific type are selected, add a warning to the user
        warning = ""
        if multipleVert:
            warning += "Multiple vertex shader files selected, only one will be loaded: "
            warning += vertexFile
            warning += "\n"
        if multipleFrag:
            warning += "Multiple fragment shader files selected, only one will be loaded: "
            warning += fragmentFile
            warning += "\n"
        if not vertexFile and not fragmentFile:
            warning += "No files with the expected extensions (*.frag *.vert) selected"
        # Load the selected shaders into the text boxes
        if vertexFile:
            with open(vertexFile, 'r') as vf:
                self.vertBox.setPlainText(vf.read())
        if fragmentFile:
            with open(fragmentFile, 'r') as ff:
                self.fragBox.setPlainText(ff.read())
        # Display the warning if any
        if warning:
            self.errBox.setPlainText(warning)

    def saveFile(self):
        # Open a file save dialog
        file = QFileDialog.getSaveFileName(
            self,
            "Save File",
            Krita.getAppDataLocation() + "/pykrita/kritamoderngl",
            "Shaders (*.vert *.frag)")
        # Get the extension of the file to save
        ext =  file[0].rsplit(".", 1)[1]
        # If it ends in .vert or .frag, use the beginning as the file name for both
        if ext.lower() == "vert" or ext.lower() == "frag":
            file = file[0].rsplit(".", 1)[0]
        # Write the contents of the text boxes to files
        with open(file + ".vert", 'w') as vf:
            vf.write(self.vertBox.toPlainText())
        with open(file + ".frag", 'w') as ff:
            ff.write(self.fragBox.toPlainText())

    def saveAndReject(self):
        self.saveSettings()
        self.reject()

    def closeEvent(self, event):
        self.saveSettings()
        event.accept()

    def saveSettings(self):
        rect = QRect(
            self.geometry().x() - self.geometryDelta.x(),
            self.geometry().y() - self.geometryDelta.y(),
            self.geometry().width() - self.geometryDelta.width(),
            self.geometry().height() - self.geometryDelta.height())
        self.ext.settings.setValue("mgl_geometry", rect)
        self.ext.settings.setValue("mgl_vert_number", self.vertNumber.text())
        if self.vertBox.toPlainText() != "":
            self.ext.settings.setValue("mgl_vert_shader", self.vertBox.toPlainText())
        if self.fragBox.toPlainText() != "":
            self.ext.settings.setValue("mgl_frag_shader", self.fragBox.toPlainText())
        self.ext.settings.sync()

    def readSettings(self):
        self.readGeometry = self.ext.settings.value("mgl_geometry", QRect(200, 200, 800, 800))
        self.setGeometry(self.readGeometry)
        self.vertNumber.setText(self.ext.settings.value("mgl_vert_number", "-1"))
        self.vertBox.setPlainText(self.ext.settings.value("mgl_vert_shader", ""))
        self.fragBox.setPlainText(self.ext.settings.value("mgl_frag_shader", ""))
from krita import *
from zipfile import ZipFile
from . import RenderShaderDialog, ComputeShaderDialog
import logging
import platform
import sys
import os

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
            self.log.info("ModernGL initialized, GL_VENDOR: %s, GL_RENDERER: %s, GL_VERSION: %s", self.ctx.info["GL_VENDOR"], self.ctx.info["GL_RENDERER"], self.ctx.info["GL_VERSION"])
        except ImportError as e:
            self.log.warning("Failed to import ModernGL: %s", str(e))

    def setup(self):
        pass

    def RenderShaderAction(self):
        configPath = QStandardPaths.writableLocation(QStandardPaths.GenericConfigLocation)
        self.settings = QSettings(configPath + '/krita-scripterrc', QSettings.IniFormat)
        self.mainDialog = RenderShaderDialog.RenderShaderDialog(self)

    def ComputeShaderAction(self):
        configPath = QStandardPaths.writableLocation(QStandardPaths.GenericConfigLocation)
        self.settings = QSettings(configPath + '/krita-scripterrc', QSettings.IniFormat)
        self.mainDialog = ComputeShaderDialog.ComputeShaderDialog(self)

    def createActions(self, window):
        mainAction = window.createAction("KritaModernGL_Render", "OpenGL Render Shader Programming")
        mainAction.triggered.connect(self.RenderShaderAction)
        mainAction = window.createAction("KritaModernGL_Compute", "OpenGL Compute Shader Programming")
        mainAction.triggered.connect(self.ComputeShaderAction)

Krita.instance().addExtension(KritaModernGL(Krita.instance()))

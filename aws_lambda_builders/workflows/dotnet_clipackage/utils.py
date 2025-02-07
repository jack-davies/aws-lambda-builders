"""
Commonly used utilities
"""
import logging
import os
import platform
import subprocess
import zipfile

from aws_lambda_builders.utils import which

LOG = logging.getLogger(__name__)


class OSUtils(object):
    """
    Convenience wrapper around common system functions
    """

    def popen(self, command, stdout=None, stderr=None, env=None, cwd=None):
        p = subprocess.Popen(command, stdout=stdout, stderr=stderr, env=env, cwd=cwd)
        return p

    def is_windows(self):
        return platform.system().lower() == "windows"

    def which(self, executable, executable_search_paths=None):
        return which(executable, executable_search_paths=executable_search_paths)

    def unzip(self, zip_file_path, output_dir, permission=None):
        """
        This method and dependent methods were copied from SAM CLI, but with the addition of deleting the zip file
        https://github.com/aws/aws-sam-cli/blob/458076265651237a662a372f54d5b3df49fd6797/samcli/local/lambdafn/zip.py#L81

        Unzip the given file into the given directory while preserving file permissions in the process.
        Parameters
        ----------
        zip_file_path : str
            Path to the zip file
        output_dir : str
            Path to the directory where the it should be unzipped to
        permission : int
            Permission to set in an octal int form
        """

        with zipfile.ZipFile(zip_file_path, "r") as zip_ref:
            # For each item in the zip file, extract the file and set permissions if available
            for file_info in zip_ref.infolist():
                extracted_path = self._extract(file_info, output_dir, zip_ref)

                # If the extracted_path is a symlink, do not set the permissions. If the target of the symlink does not
                # exist, then os.chmod will fail with FileNotFoundError
                if not os.path.islink(extracted_path):
                    self._set_permissions(file_info, extracted_path)
                    self._override_permissions(extracted_path, permission)

        if not os.path.islink(extracted_path):
            self._override_permissions(output_dir, permission)

        os.remove(zip_file_path)

    def _is_symlink(self, file_info):
        """
        Check the upper 4 bits of the external attribute for a symlink.
        See: https://unix.stackexchange.com/questions/14705/the-zip-formats-external-file-attribute
        Parameters
        ----------
        file_info : zipfile.ZipInfo
            The ZipInfo for a ZipFile
        Returns
        -------
        bool
            A response regarding whether the ZipInfo defines a symlink or not.
        """
        symlink = 0xA
        return (file_info.external_attr >> 28) == symlink

    def _extract(self, file_info, output_dir, zip_ref):
        """
        Unzip the given file into the given directory while preserving file permissions in the process.
        Parameters
        ----------
        file_info : zipfile.ZipInfo
            The ZipInfo for a ZipFile
        output_dir : str
            Path to the directory where the it should be unzipped to
        zip_ref : zipfile.ZipFile
            The ZipFile we are working with.
        Returns
        -------
        string
            Returns the target path the Zip Entry was extracted to.
        """

        # Handle any regular file/directory entries
        if not self._is_symlink(file_info):
            return zip_ref.extract(file_info, output_dir)

        source = zip_ref.read(file_info.filename).decode("utf8")
        link_name = os.path.normpath(os.path.join(output_dir, file_info.filename))

        # make leading dirs if needed
        leading_dirs = os.path.dirname(link_name)
        if not os.path.exists(leading_dirs):
            os.makedirs(leading_dirs)

        # If the link already exists, delete it or symlink() fails
        if os.path.lexists(link_name):
            os.remove(link_name)

        # Create a symbolic link pointing to source named link_name.
        os.symlink(source, link_name)

        return link_name

    def _override_permissions(self, path, permission):
        """
        Forcefully override the permissions on the path
        Parameters
        ----------
        path str
            Path where the file or directory
        permission octal int
            Permission to set
        """
        if permission:
            os.chmod(path, permission)

    def _set_permissions(self, zip_file_info, extracted_path):
        """
        Sets permissions on the extracted file by reading the ``external_attr`` property of given file info.
        Parameters
        ----------
        zip_file_info : zipfile.ZipInfo
            Object containing information about a file within a zip archive
        extracted_path : str
            Path where the file has been extracted to
        """

        # Permission information is stored in first two bytes.
        permission = zip_file_info.external_attr >> 16
        if not permission:
            # Zips created on certain Windows machines, however, might not have any permission information on them.
            # Skip setting a permission on these files.
            LOG.debug("File %s in zipfile does not have permission information", zip_file_info.filename)
            return

        os.chmod(extracted_path, permission)

    @property
    def pipe(self):
        return subprocess.PIPE

from pathlib import Path
import logging
from farm.data_handler.utils import http_get
import tempfile
import tarfile
import zipfile
from typing import Callable
from haystack.indexing.file_converters.pdftotext import PDFToText
from haystack.database.base import Document

logger = logging.getLogger(__name__)


def convert_files_to_documents(dir_path: str, clean_func: Callable = None, split_paragraphs: bool = False) -> [Document]:
    """
    Convert all files(.txt, .pdf) in the sub-directories of the given path to Document objects.

    :param dir_path: path for the documents to be written to the database
    :param clean_func: a custom cleaning function that gets applied to each doc (input: str, output:str)
    :param split_paragraphs: split text in paragraphs.

    :return: None
    """

    file_paths = []
    for ext in ("**/*.txt", "**/*.pdf"):
        paths = [p for p in Path(dir_path).glob(ext)]
        file_paths.extend(paths)
        if ".pdf" in [p.suffix for p in paths]:
            pdf_converter = PDFToText()
        else:
            pdf_converter = None

    documents = []
    for path in file_paths:
        if path.suffix == ".txt":
            with open(path) as doc:
                text = doc.read()
        elif path.suffix == ".pdf":
            text = pdf_converter.extract_text(path)
        else:
            raise Exception(f"Indexing of {path.suffix} files is not currently supported.")

        if clean_func:
            text = clean_func(text)

        if split_paragraphs:
            for para in text.split("\n\n"):
                if not para.strip():  # skip empty paragraphs
                    continue
                documents.append(Document(text=para))
        else:
            documents.append(Document(text=text))

    return documents


def fetch_archive_from_http(url, output_dir, proxies=None):
    """
    Fetch an archive (zip or tar.gz) from a url via http and extract content to an output directory.

    :param url: http address
    :type url: str
    :param output_dir: local path
    :type output_dir: str
    :param proxies: proxies details as required by requests library
    :type proxies: dict
    :return: bool if anything got fetched
    """
    # verify & prepare local directory
    path = Path(output_dir)
    if not path.exists():
        path.mkdir(parents=True)

    is_not_empty = len(list(Path(path).rglob("*"))) > 0
    if is_not_empty:
        logger.info(
            f"Found data stored in `{output_dir}`. Delete this first if you really want to fetch new data."
        )
        return False
    else:
        logger.info(f"Fetching from {url} to `{output_dir}`")

        # download & extract
        with tempfile.NamedTemporaryFile() as temp_file:
            http_get(url, temp_file, proxies=proxies)
            temp_file.flush()
            temp_file.seek(0)  # making tempfile accessible
            # extract
            if url[-4:] == ".zip":
                archive = zipfile.ZipFile(temp_file.name)
                archive.extractall(output_dir)
            elif url[-7:] == ".tar.gz":
                archive = tarfile.open(temp_file.name)
                archive.extractall(output_dir)
            # temp_file gets deleted here
        return True


import os
import sys
import tempfile
import unittest

from unittest.mock import patch

import pytest
from io import StringIO
from azentcoder.code_utils import (
    UNKNOWN,
    content_str,
    execute_code,
    extract_code
)


from azentcoder.code_utils import (
    PATH_SEPARATOR,
    UNKNOWN,
    WIN32,
    content_str,
    execute_code,
    extract_code,
    improve_code,
    improve_function,
    infer_lang,
)

KEY_LOC = "notebook"
OAI_CONFIG_LIST = "OAI_CONFIG_LIST"
here = os.path.abspath(os.path.dirname(__file__))


def test_infer_lang():
    assert infer_lang("print('hello world')") == "python"
    assert infer_lang("pip install autogen") == "sh"

    # test infer lang for unknown code/invalid code
    assert infer_lang("dummy text") == UNKNOWN
    assert infer_lang("print('hello world'))") == UNKNOWN


def test_extract_code():
    print(extract_code("```bash\npython temp.py\n```"))
    # test extract_code from markdown
    codeblocks = extract_code(
        """
Example:
```
print("hello extract code")
```
""",
        detect_single_line_code=False,
    )
    print(codeblocks)

    codeblocks2 = extract_code(
        """
Example:
```
print("hello extract code")
```
""",
        detect_single_line_code=True,
    )
    print(codeblocks2)

    assert codeblocks2 == codeblocks
    # import pdb; pdb.set_trace()

    codeblocks = extract_code(
        """
Example:
```python
def scrape(url):
    import requests
    from bs4 import BeautifulSoup
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.find("title").text
    text = soup.find("div", {"id": "bodyContent"}).text
    return title, text
```
Test:
```python
url = "https://en.wikipedia.org/wiki/Web_scraping"
title, text = scrape(url)
print(f"Title: {title}")
print(f"Text: {text}")
```
"""
    )
    print(codeblocks)
    assert len(codeblocks) == 2 and codeblocks[0][0] == "python" and codeblocks[1][0] == "python"

    codeblocks = extract_code(
        """
Example:
``` python
def scrape(url):
    import requests
    from bs4 import BeautifulSoup
    response = requests.get(url)
    soup = BeautifulSoup(response.text, "html.parser")
    title = soup.find("title").text
    text = soup.find("div", {"id": "bodyContent"}).text
    return title, text
```
Test:
``` python
url = "https://en.wikipedia.org/wiki/Web_scraping"
title, text = scrape(url)
print(f"Title: {title}")
print(f"Text: {text}")
```
"""
    )
    print(codeblocks)
    assert len(codeblocks) == 2 and codeblocks[0][0] == "python" and codeblocks[1][0] == "python"

    # Check for indented code blocks
    codeblocks = extract_code(
        """
Example:
   ```python
   def scrape(url):
       import requests
       from bs4 import BeautifulSoup
       response = requests.get(url)
       soup = BeautifulSoup(response.text, "html.parser")
       title = soup.find("title").text
       text = soup.find("div", {"id": "bodyContent"}).text
       return title, text
   ```
"""
    )
    print(codeblocks)
    assert len(codeblocks) == 1 and codeblocks[0][0] == "python"

    # Check for codeblocks with \r\n
    codeblocks = extract_code(
        """
Example:
``` python
def scrape(url):
   import requests
   from bs4 import BeautifulSoup
   response = requests.get(url)
   soup = BeautifulSoup(response.text, "html.parser")
   title = soup.find("title").text
   text = soup.find("div", {"id": "bodyContent"}).text
   return title, text
```
""".replace(
            "\n", "\r\n"
        )
    )
    print(codeblocks)
    assert len(codeblocks) == 1 and codeblocks[0][0] == "python"

    codeblocks = extract_code("no code block")
    assert len(codeblocks) == 1 and codeblocks[0] == (UNKNOWN, "no code block")

    # Disable single line code detection
    line = "Run `source setup.sh` from terminal"
    codeblocks = extract_code(line, detect_single_line_code=False)
    assert len(codeblocks) == 1 and codeblocks[0] == (UNKNOWN, line)

    # Enable single line code detection
    codeblocks = extract_code("Run `source setup.sh` from terminal", detect_single_line_code=True)
    assert len(codeblocks) == 1 and codeblocks[0] == ("", "source setup.sh")


@pytest.mark.skipif(
    sys.platform in ["darwin"],
    reason="do not run on MacOS",
)
def test_execute_code(use_docker=None):
    try:
        import docker
    except ImportError as exc:
        print(exc)
        docker = None
    if use_docker is None:
        use_docker = docker is not None
    exit_code, msg, image = execute_code("print('hello world')", filename="tmp/codetest.py", use_docker=use_docker)
    assert exit_code == 0 and msg == "hello world\n", msg
    # read a file
    print(execute_code("with open('tmp/codetest.py', 'r') as f: a=f.read()", use_docker=use_docker))
    # create a file
    exit_code, msg, image = execute_code(
        "with open('tmp/codetest.py', 'w') as f: f.write('b=1')",
        work_dir=f"{here}/my_tmp",
        filename="tmp2/codetest.py",
        use_docker=use_docker,
    )
    assert exit_code and (
        'File "tmp2/codetest.py"'.replace("/", PATH_SEPARATOR) in msg
        or 'File ".\\tmp2/codetest.py' in msg  # py3.8 + win32
    ), msg
    print(
        execute_code(
            "with open('tmp/codetest.py', 'w') as f: f.write('b=1')", work_dir=f"{here}/my_tmp", use_docker=use_docker
        )
    )
    # execute code in a file
    print(execute_code(filename="tmp/codetest.py", use_docker=use_docker))
    print(execute_code("python tmp/codetest.py", lang="sh", use_docker=use_docker))
    # execute code for assertion error
    exit_code, msg, image = execute_code("assert 1==2", use_docker=use_docker)
    assert exit_code, msg
    assert 'File ""' in msg or 'File ".\\"' in msg  # py3.8 + win32
    # execute code which takes a long time
    exit_code, error, image = execute_code("import time; time.sleep(2)", timeout=1, use_docker=use_docker)
    assert exit_code and error == "Timeout" or WIN32
    assert isinstance(image, str) or docker is None or os.path.exists("/.dockerenv") or use_docker is False


def test_execute_code_raises_when_code_and_filename_are_both_none():
    with pytest.raises(AssertionError):
        execute_code(code=None, filename=None)


@pytest.mark.skipif(
    sys.platform in ["darwin"],
    reason="do not run on MacOS",
)
def test_execute_code_nodocker():
    test_execute_code(use_docker=False)


def test_execute_code_no_docker():
    exit_code, error, image = execute_code("import time; time.sleep(2)", timeout=1, use_docker=False)
    if sys.platform != "win32":
        assert exit_code and error == "Timeout"
    assert image is None


def _test_improve():
    try:
        import openai
    except ImportError:
        return
    config_list = autogen.config_list_openai_aoai(KEY_LOC)
    improved, _ = improve_function(
        "autogen/math_utils.py",
        "solve_problem",
        "Solve math problems accurately, by avoiding calculation errors and reduce reasoning errors.",
        config_list=config_list,
    )
    with open(f"{here}/math_utils.py.improved", "w") as f:
        f.write(improved)
    suggestion, _ = improve_code(
        ["autogen/code_utils.py", "autogen/math_utils.py"],
        "leverage generative AI smartly and cost-effectively",
        config_list=config_list,
    )
    print(suggestion)
    improvement, cost = improve_code(
        ["autogen/code_utils.py", "autogen/math_utils.py"],
        "leverage generative AI smartly and cost-effectively",
        suggest_only=False,
        config_list=config_list,
    )
    print(cost)
    with open(f"{here}/suggested_improvement.txt", "w") as f:
        f.write(improvement)


class TestContentStr(unittest.TestCase):
    def test_string_content(self):
        self.assertEqual(content_str("simple string"), "simple string")

    def test_list_of_text_content(self):
        content = [{"type": "text", "text": "hello"}, {"type": "text", "text": " world"}]
        self.assertEqual(content_str(content), "hello world")

    def test_mixed_content(self):
        content = [{"type": "text", "text": "hello"}, {"type": "image_url", "url": "http://example.com/image.png"}]
        self.assertEqual(content_str(content), "hello<image>")

    def test_invalid_content(self):
        content = [{"type": "text", "text": "hello"}, {"type": "wrong_type", "url": "http://example.com/image.png"}]
        with self.assertRaises(AssertionError) as context:
            content_str(content)
        self.assertIn("Wrong content format", str(context.exception))

    def test_empty_list(self):
        self.assertEqual(content_str([]), "")

    def test_non_dict_in_list(self):
        content = ["string", {"type": "text", "text": "text"}]
        with self.assertRaises(TypeError):
            content_str(content)


if __name__ == "__main__":
    test_infer_lang()
    # test_extract_code()
    # test_execute_code()
    # test_find_code()
    # unittest.main()

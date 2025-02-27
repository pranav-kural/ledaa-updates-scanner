import requests
from bs4 import BeautifulSoup
import hashlib
import boto3
import markdownify

# Constants
BASE_URL = "https://fragment.dev/docs"
HASHES_TABLE = "fragment-docs-hashes"

# Extracts HTML from the section that contains the primary documentation content specific to the topic of URL
def get_primary_section_html(url: str):
    """
    This method fetches and extracts HTML from the section that contains the primary documentation content specific to the topic of URL.

    :param str url: The URL of the page to scrape

    :return BeautifulSoup: The primary section content as a BeautifulSoup object
    """
    # Fetch the page content
    response = requests.get(url)
    if response.status_code != 200:
        print(f"Error: Failed to fetch URL: {url}")
        return ""
    # Parse the HTML content
    soup = BeautifulSoup(response.text, "html.parser")

    # Locate the primary content
    main_content_div = soup.find("div", class_="basis-full")
    if not main_content_div:
        print(f"Warning: No main content found for {url}")
        return ""
    # Extract section
    primary_section = main_content_div.find("section")
    if not primary_section:
        print(f"Warning: No section found in main content for {url}")
        return ""

    return primary_section

# Processes the primary section content HTML and converts it to markdown
def process_primary_section_content(primary_section):
    """
    This method processes the primary section content HTML and converts it to markdown with proper formatting.

    Inline and block code snippets are converted to markdown code blocks.
    Images are converted to markdown image links.

    :param BeautifulSoup primary_section: The primary section content as a BeautifulSoup object

    :return str: The markdown content
    """
    # Convert <pre><code> blocks to markdown fenced code blocks
    for pre in primary_section.find_all("pre"):
        code_block = pre.find("code")
        if code_block:
            language = "bash"  # Default language
            if "class" in code_block.attrs:
                classes = code_block["class"]
                for c in classes:
                    if c.startswith("language-"):
                        language = c.split("language-")[1]
                        break

            code_text = code_block.get_text()
            markdown_code = f"\n```{language}\n{code_text}\n```\n"
            pre.replace_with(markdown_code)

    # Handle <code> blocks that are NOT inside <pre>
    for code in primary_section.find_all("code"):
        code_text = code.get_text()
        if "data-testid" in code.attrs and code["data-testid"] == "inline-code":
            markdown_inline = f"`{code_text}`"
            code.replace_with(markdown_inline)
        else:
            language = "bash"
            if "class" in code.attrs:
                classes = code["class"]
                for c in classes:
                    if c.startswith("language-"):
                        language = c.split("language-")[1]
                        break
            markdown_code = f"\n```{language}\n{code_text}\n```\n"
            code.replace_with(markdown_code)

    # Convert images to markdown
    for img in primary_section.find_all("img"):
        img_url = img["src"]
        img.replace_with(f"![Image]({img_url})")

    # Convert filtered HTML to Markdown
    markdown_content = markdownify.markdownify(str(primary_section), heading_style="ATX")

    return markdown_content

# Generates a hash of the content for a given URL and compares it with the existing hash in DynamoDB
def generate_and_compare_hash(url: str, content: str):
    """
    This method generates a hash of the content for a given URL and compares it with the existing hash in DynamoDB.

    :param str url: The URL of the page
    :param str content: The content of the page

    :return bool: True if the hash has changed, False otherwise
    """
    # Generate a hash of the content
    hash_content = hashlib.sha256(content.encode('utf-8')).hexdigest()

    # Fetch the existing hash from DynamoDB
    try:
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.Table(HASHES_TABLE)
        response = table.get_item(Key={'id': url})
        if 'Item' in response:
            existing_hash = response['Item']['hash']
            print(f"Existing hash: {existing_hash}")
            print(f"Current hash: {hash_content}")
            if existing_hash == hash_content:
                print(f"Hash has not changed for {url}")
                return False
            else:
                print(f"Hash has changed for {url}")
                return True
        else:
            print(f"No existing hash found for {url}")
            return True
    except Exception as e:
        raise Exception(f"An error occurred while fetching the hash: {e}")

# Main method to scrape the URL and compare the hash of current content with the existing hash
def scrape_url_and_compare_hash(url: str):
    """
    This method scrapes the content of the URL and compares the hash of the current content with the existing hash.

    :param str url: The URL of the page to scrape
    """
    print(f"Scraping URL: {url}")
    # Get the primary section content
    primary_section = get_primary_section_html(url)
    print("Primary section HTML extracted")
    if not primary_section:
        raise Exception(f"Error: No primary section found for {url}")
    # Generate markdown content
    markdown_content = process_primary_section_content(primary_section)
    print("Markdown content generated")
    if not markdown_content:
        raise Exception(f"Error: No markdown content generated for {url}")
    
    # Generate and compare hash of primary content
    print("Generating and comparing hashes")
    has_hash_changed = generate_and_compare_hash(url, markdown_content)

    # If hash has changed, invoke the ledaa_load_data Lambda function passing it the URL
    if has_hash_changed:
        print(f"Invoking LEDAA Load Data Lambda for {url}")
        lambda_client = boto3.client('lambda')
        try:
            lambda_invoke_status_response = lambda_client.invoke(
                FunctionName='ledaa_load_data',
                InvocationType='Event',
                Payload='{"url": "' + url + '"}'
            )
            # check invocation status
            if lambda_invoke_status_response['StatusCode'] != 202:
                print(f"Error: Failed to invoke LEDAA Load Data Lambda for {url}")
                # Log the error
                print(lambda_invoke_status_response)
            else:
                print(f"LEDAA Load Data Lambda invoked successfully for {url}")
        except Exception as e:
            print(f"An error occurred while invoking LEDAA Load Data Lambda: {e}")

# Get all the links to the documentation pages
def get_all_doc_links():
    response = requests.get(BASE_URL)
    soup = BeautifulSoup(response.text, "html.parser")
    links = [a['href'] for a in soup.find_all('a', href=True) if a['href'].startswith('/docs')]
    return list(set(["https://fragment.dev" + link for link in links]))

# Lambda handler method (will be invoked by AWS Lambda)
def lambda_handler(event, context):
    print("LEDAA Updates Scanner Lambda invoked")
    # Scrape the URL and compare the hash for each documentation page
    urls = get_all_doc_links()
    for url in urls:
        scrape_url_and_compare_hash(url)
    return {
        'statusCode': 200,
        'body': 'Scraping completed'
    }

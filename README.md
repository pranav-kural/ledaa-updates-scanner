# LEDAA Updates Scanner

LEDAA project is about building a conversational AI assistant for [FRAGMENT (documentation)](https://fragment.dev/docs). 

**LEDAA Updates Scanner** component scraps HTML from a given specific [FRAGMENT (documentation)](https://fragment.dev/docs) webpage and then:

1. Extracts HTML for primary section (i.e., section of importance, excluding header, footer, etc.).
2. Generates SHA-256 hash of the primary section HTML.
3. Compares the generated hash with the hash stored in **AWS DynamoDB** table for the given `URL`.
4. If the hash is different, the program initiates the process of **data loading** (i.e., scrapping primary section HTML, markdown data preparation, embedding generation, and vector store update of chunks associated with the given `URL`). Data loading is handled by a separate Lambda function.

Basically, this programs acts as a sort of scanner that initiates the data loading process for a specific URL when it detects that the data for that URL has changed. This ensures that the knowledge base (vector store data) for the RAG-pipeline supporting conversational applications for Ledger API documentation is always up-to-date. The data on the Ledger API's documentation website is considered the **Single Source of Truth**.

This scanner function is deployed as an **AWS Lambda** function and is triggered at a specific interval using **AWS EventBridge Schedule**.

To learn more check: [Building AI Assistant for FRAGMENT documentation](https://www.pkural.ca/blog/posts/fragment/)

![ledaa-updates-scanner](https://github.com/user-attachments/assets/4a28c20a-4e1b-4875-833d-b8ebd1d2d029)

## Updates Scanner Process Flow

1. **Web Scraping**: The program receives `URL` of the webpage as an argument and uses `BeautifulSoup` to scrap HTML data from the given URL.
2. **Primary Section HTML Extraction**: First, we extract the HTML of only the section of the documentation page we are concerned with, i.e., we exclude the header, footer, and other irrelevant sections.
3. **Hash Generation**: We generate a SHA-256 hash of the primary section HTML.
4. **Hash Comparison**: We compare the generated hash with the hash stored in the **AWS DynamoDB** table for the given `URL`.
5. **Data Loading**: If the hash is different, we initiate the process of data loading for the given `URL`.

Code for the above steps can be found in the `core.py` file.

## Overall LEDAA Data Process Flow

Below is the process flow for how ground truth data updates are handled and how the knowledge base is effectively updated.

1. [`ledaa_updates_scanner`](https://github.com/pranav-kural/ledaa-updates-scanner) Lambda function monitors for changes in content of documentation.
2. On detecting changes, it triggers the [`ledaa_load_data`](https://github.com/pranav-kural/ledaa-load-data) Lambda function passing it the URL of webpage.
3. `ledaa_load_data` Lambda function invokes the [`ledaa_text_splitter`](https://github.com/pranav-kural/ledaa-text-splitter) Lambda function to initiate the process of scraping data from a given URL and to get a list of strings (representing text chunks or documents) which will be used in data ingestion.
4. `ledaa_text_splitter` Lambda function invokes the [`ledaa_web_scrapper`](https://github.com/pranav-kural/ledaa-web-scrapper) Lambda function to scrape the URL and store the processed markdown data in S3. `ledaa_web_scrapper` function also stores the hash of the processed data in DynamoDB which will later be compared by `ledaa_updates_scanner` function to detect changes.
5. On receiving processed document chunks back, `ledaa_load_data` Lambda function stores the data in the vector store.

## AWS Lambda Deployment

We deploy the scanner function to AWS Lambda using [Terraform](https://www.terraform.io/). The Terraform configuration files can be found in the `terraform` directory. The configuration file creates:

-   Appropriate AWS role and policy for the Lambda function.
-   AWS Lambda Layer for the Lambda function using pre-built compressed lambda layer zip file (present in `terraform/packages`, created using `create_lambda_layer.sh`).
-   Data archive file for the core code (`core.py`).
-   AWS Lambda function using the data archive file, the Lambda Layer, and the appropriate role.
-   Lambda function is configured appropriately to access **AWS DynamoDB**.
-   Appropriate AWS role and policy for the AWS EventBridge Schedule.
-   **AWS EventBridge Schedule** to trigger the Lambda function at a specific interval.

There are certain scripts in `terraform` directory, like `apply.sh` and `plan.sh`, which can be used to apply and plan the Terraform configuration respectively. These scripts extract necessary environment variables from the `.env` file and pass them to Terraform.

Ideally, this Lambda function will be triggered by another Lambda function which is responsible for monitoring documentation updates.

## LICENSE

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

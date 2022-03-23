# covid-dashboard

A COVID-19 dashboard for the London Borough of Lewisham, hosted on Github Pages. 

This fetches daily coronavirus case numbers for Lewisham from the U.K. Coronavirus Dashboard API:
https://coronavirus.data.gov.uk/details/developers-guide/main-api

Updates are scheduled as Github Actions, and the resulting documents are published to the Git branch `gh-pages`, where they can be published via Github Pages. 

To serve Github Pages on a custom domain, create a new repository secret called `PAGES_CNAME` and set its value to the name of your custom domain, such as `example.com`. This will generate a CNAME file in the `gh-pages` branch during every refresh. Manually trigger the Github Action if needed to generate this file for the first time, then enable your custom domain in your project's Github Pages settings.

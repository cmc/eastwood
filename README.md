# Eastwood


It's a wild place out there. There are probably a crew of less-than-well-intentioned individuals typo squatting your domains trying to phish your users. You need to locate those domains, fire off some takedown/suspension requests to the registrar, and perhaps seize the domain via UDRP/$insert_legal_entity_here.

Eastwood runs as a service, every hour it pulls the updated zone files for all top level TLDs.

It then matches them against your specified brand names. It sends findings to Slack & stores entries in a database.

You'll be notified of all new domains infringing on your name[s] daily.

eastwood is a sister project of [denzel](https://github.com/cmc/denzel), which will receive POSTs from eastwood and check the discovered site for similarity to your legitimate site using ssdeep fuzzy hashing.

Coming soon - 
   - Queued & approved dispatch of takedown emails for identified hostile sites to registrars.

# Quickstart
To deploy this application you require a Postgresql DB to store DNS entries. We provide that to you here through a docker-compose file. If you have docker-compose installed and would like to run this locally on your laptop, simply configure the application and run `make image` followed by a `make compose`

### Step By Step
   - Get a zonefiles.io api key
   - copy config/config.json.example to config/config.json
   - add zonefile / keys
   - add slack webhook to config
   - `make image`
   - `make compose`
 

<img src="https://github.com/cmc/eastwood/blob/master/images/clint-eastwood.jpg" width="1000" height="800">

# Search dorks

Run each set through WebSearch first. Open the browser (google.com, bing.com,
duckduckgo.com, yandex.com) when results are thin or a query needs operators that
WebSearch drops. Quote the selector exactly. Record the query, the URL and the snippet
that ties it to the selector.

## Any selector

```
"<selector>"
"<selector>" -site:<the selector's own site>
"<selector>" site:pastebin.com OR site:ghostbin.com OR site:rentry.co
"<selector>" filetype:pdf OR filetype:doc OR filetype:docx OR filetype:xls OR filetype:xlsx
"<selector>" site:github.com OR site:gitlab.com OR site:stackoverflow.com
"<selector>" site:reddit.com OR site:news.ycombinator.com
"<selector>" site:linkedin.com
"<selector>" scam OR fraud OR phishing OR spam
```

## Email

```
"<local>@<domain>"
"<local>" "<domain>"                       # addresses written as "name at domain"
"<local> at <domain>" OR "<local>[at]<domain>"
site:<domain> "<local>"                    # org domains: staff pages, papers, press releases
"@<domain>" -site:<domain>                 # who else uses a small custom domain
```

## Username

```
"<user>"
intitle:"<user>"
inurl:"<user>" -site:<sites already checked>
"<user>" "real name" OR "my name is" OR "contact"
"<user>" (resume OR cv OR portfolio)
```

## IP

```
"<ip>"
"<ip>" (abuse OR attack OR scanner OR botnet)
"<ip>" site:github.com                     # IPs in published blocklists or configs
"<first three octets>." site:pastebin.com  # neighbouring IPs in the same campaign
```

## Name found by pivoting

When a real name turns up, search it with the context that ties it to the selector
(employer, city, the handle), never the bare name alone:

```
"<first> <last>" "<employer>"
"<first> <last>" "<user>"
"<first> <last>" site:linkedin.com "<city or employer>"
```

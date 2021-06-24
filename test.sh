#!/usr/bin/env bash
sam build --use-container
sam local invoke MentionsToEpubsFunction
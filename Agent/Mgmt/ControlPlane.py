import requests
from Agent.Data.APISubscription import APISubscription
from Agent.Data.Publisher import Publisher
from Agent.Data.APIVersion import APIVersion
from Agent.Data.Offer import Offer

GET_PROJECT_FILE_URL_URL_FORMAT = "{base_url}/api/aiagents/{agent_id}/subscriptions/{subscription_id}/projectFileUrl/{version_name}"
GET_AGENT_SUBSCRIPTIONS_URL_FORMAT = "{base_url}/api/aiagents/{agent_id}/subscriptions"
GET_AGENT_APIVERSIONS_URL_FORMAT = "{base_url}/api/aiagents/{agent_id}/apiVersions"
GET_AGENT_OFFERS_URL_FORMAT = "{base_url}/api/aiagents/{agent_id}/offers"

class ControlPlane(object):
    """description of class"""

    def __init__(self, agentId, agentKey):
        self._agentId = agentId
        self._agentKey = agentKey
        return

    def GetProjectFileUrl(self, subscriptionId, versionName, controlPlanUrl):
        requestUrl = GET_PROJECT_FILE_URL_URL_FORMAT.format(base_url=controlPlanUrl, agent_id=self._agentId, subscription_id=subscriptionId, version_name=versionName)
        response = requests.get(requestUrl, headers=self.GetAuthHeader())
        if response.status_code == 200:
            url = response.text
        return url

    def GetAgentSubscriptionsFromControlPlane(self, controlPlaneUrl):
        requestUrl = GET_AGENT_SUBSCRIPTIONS_URL_FORMAT.format(base_url=controlPlaneUrl, agent_id=self._agentId)
        response = requests.get(requestUrl, headers=self.GetAuthHeader())
        if response.status_code == 200:
            subscriptions = response.json()

        return subscriptions

    def GetAgentAPIVersionsFromControlPlane(self, controlPlaneUrl):
        requestUrl = GET_AGENT_APIVERSIONS_URL_FORMAT.format(base_url=controlPlaneUrl, agent_id=self._agentId)
        response = requests.get(requestUrl, headers=self.GetAuthHeader())
        if response.status_code == 200:
            apiversions = response.json()

        return apiversions
    
    def GetAgentOffersFromControlPlane(self, controlPlaneUrl):
        requestUrl = GET_AGENT_OFFERS_URL_FORMAT.format(base_url=controlPlaneUrl, agent_id=self._agentId)
        response = requests.get(requestUrl, headers=self.GetAuthHeader())
        if response.status_code == 200:
            offers = response.json()

        return offers

    def GetAuthHeader(self):
        return {"Authorization": self._agentKey}

    def UpdateMetadataDatabase(self):
        publishers = Publisher.ListAll()
        for publisher in publishers:
            subscriptions = self.GetAgentSubscriptionsFromControlPlane(publisher.ControlPlaneUrl)
            APISubscription.MergeWithDelete(subscriptions, publisher.PublisherId)
            apiVersions = self.GetAgentAPIVersionsFromControlPlane(publisher.ControlPlaneUrl)
            APIVersion.MergeWithDelete(apiVersions, publisher.PublisherId)
            offers = self.GetAgentOffersFromControlPlane(publisher.ControlPlaneUrl)
            Offer.MergeWithDelete(offers, publisher.PublisherId)
        return





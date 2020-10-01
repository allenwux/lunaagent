from sqlalchemy import Column, Integer, String
from Agent import Base, Session
import jwt, datetime, os

class Offer(Base):
    """description of class"""
    
    __tablename__ = 'agent_offers'

    Id = Column(Integer, primary_key = True)

    OfferId = Column(String)

    OfferName = Column(String)

    PublisherId = Column(String)

    PublisherMicrosoftId = Column(String)

    PublisherName = Column(String)

    Description = Column(String)

    LogoImageUrl = Column(String)
    
    DocumentationUrl = Column(String)

    LandingPageUrl = Column(String)

    SubscribePageUrl = ""

    OfferType = Column(String)

    LastUpdatedTime = Column(String)

    CreatedTime = Column(String)

    @staticmethod
    def ListMarketplaceOffers(userId):
        session = Session()
        offers = session.query(Offer).filter_by(OfferType = 'Marketplace').all()
        session.close()
        for offer in offers:
            offer.SubscribePageUrl = "https://ms.portal.azure.com/#create/{}.{}/preview".format(offer.PublisherMicrosoftId, offer.OfferId)
        return offers

    @staticmethod
    def GetToken(offer, userId):
        expired_time = (datetime.datetime.utcnow() + datetime.timedelta(days = 1)).timestamp()
        encoded_jwt = jwt.encode({'prod':offer.OfferId, 'uid':userId, 'exp':str(expired_time), 'iss':os.environ['AGENT_ID'], 'url':os.environ['AGENT_API_ENDPOINT']}, 
            os.environ['AGENT_KEY'], algorithm='HS256', 
            headers={'alg': 'HS256', 'aid':os.environ['AGENT_ID'], 'src':'lunaagent'})
        return str(encoded_jwt)[2:-1]

    @staticmethod
    def ListInternalOffers(userId):
        session = Session()
        offers = session.query(Offer).filter_by(OfferType = 'Internal').all()
        session.close()
        for offer in offers:
            offer.SubscribePageUrl = "{}?token={}".format(offer.LandingPageUrl, Offer.GetToken(offer, userId))
        return offers

    @staticmethod
    def MergeWithDelete(offers, publisherId):
        session = Session()
        try:
            dbOffers = session.query(Offer).all()
            for dbOffer in dbOffers:
                if dbOffer.PublisherId.lower() != publisherId.lower():
                    continue;
                # If the offer is removed in the control plane, remove it from the agent
                try:
                    next(item for item in offers if 
                         item["OfferId"] == dbOffer.OfferId
                         and item["PublisherId"].lower() == dbOffer.PublisherId.lower())
                except StopIteration:
                    session.delete(dbOffer)

            for offer in offers:
                dbOffer = session.query(Offer).filter_by(OfferId = offer["OfferId"], 
                                                                   PublisherId = offer["PublisherId"]).first()
                if dbOffer:
                    dbOffer.Description = offer["Description"]
                    
                    if "LogoImageUrl" in offer:
                        dbOffer.LogoImageUrl = offer["LogoImageUrl"]

                    dbOffer.OfferName = offer["OfferName"]
                    if "DocumentationUrl" in offer:
                        dbOffer.DocumentationUrl = offer["DocumentationUrl"]

                    dbOffer.PublisherName = offer["PublisherName"]
                    dbOffer.LandingPageUrl = offer["LandingPageUrl"]
                    dbOffer.LastUpdatedTime = offer["LastUpdatedTime"]
                    dbOffer.CreatedTime = offer["CreatedTime"]
                    if "PublisherMicrosoftId" in offer:
                        dbOffer.PublisherMicrosoftId = offer["PublisherMicrosoftId"]

                else:
                    dbOffer = Offer(**offer)
                    session.add(dbOffer)

            session.commit()
        except Exception as e:
            session.rollback()
            raise

        finally:
            session.close()

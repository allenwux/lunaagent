from sqlalchemy import Column, Integer, String
from Agent import Base, Session

class Publisher(Base):
    """description of class"""
    
    __tablename__ = 'agent_publishers'
    Id = Column(Integer, primary_key = True)

    PublisherId = Column(Integer)

    ControlPlaneUrl = Column(String)

    Name = Column(String)

    @staticmethod
    def Create(publisher):
        session = Session()
        session.add(publisher)
        session.commit()
        session.close()
        return

    @staticmethod
    def Update(publisherId, publisher):
        session = Session()
        dbPublisher = session.query(Publisher).filter_by(PublisherId = publisherId).first()
        dbPublisher.ControlPlaneUrl = publisher.ControlPlaneUrl
        dbPublisher.Name = publisher.Name
        session.commit()
        session.close()
        return publisher.ControlPlaneUrl

    @staticmethod
    def ListAll():
        session = Session()
        publishers = session.query(Publisher).all()
        session.close()
        return publishers
    
    @staticmethod
    def Get(publisherId):
        session = Session()
        publisher = session.query(Publisher).filter_by(PublisherId = publisherId).first()
        session.close()
        return publisher

    @staticmethod
    def Delete(publisherId):
        session = Session()
        publisher = Publisher.Get(publisherId)
        session.delete(publisher)
        session.commit()
        session.close()
        return
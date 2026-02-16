"""Marketing models – Listing, Lead, Application, Screening."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Date, Numeric, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base


class LeadSource(Base):
    __tablename__ = "lead_sources"
    id = Column(Integer, primary_key=True, autoincrement=True)
    source_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())


class ListingChannel(Base):
    __tablename__ = "listing_channels"
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel_name = Column(String(100), nullable=False)
    is_active = Column(Boolean, default=True)
    api_endpoint = Column(String(500))
    created_at = Column(DateTime, server_default=func.now())


class Listing(Base):
    __tablename__ = "listings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    unit_id = Column(Integer, ForeignKey("units.id"))
    property_id = Column(Integer, ForeignKey("properties.id"))
    listing_title = Column(String(300), nullable=False)
    listing_description = Column(Text)
    rent_from = Column(Numeric(14, 2))
    rent_to = Column(Numeric(14, 2))
    currency = Column(String(10), default="USD")
    is_published = Column(Boolean, default=False)
    listed_date = Column(Date)
    days_on_market = Column(Integer, default=0)
    photo_urls = Column(Text)
    virtual_tour_url = Column(String(500))
    status = Column(String(20), default="Draft")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ListingChannelLink(Base):
    __tablename__ = "listing_channel_links"
    id = Column(Integer, primary_key=True, autoincrement=True)
    listing_id = Column(Integer, ForeignKey("listings.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("listing_channels.id"), nullable=False)
    external_listing_url = Column(String(500))
    sync_status = Column(String(20), default="Pending")
    created_at = Column(DateTime, server_default=func.now())


class Lead(Base):
    __tablename__ = "leads"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    listing_id = Column(Integer, ForeignKey("listings.id"))
    unit_id = Column(Integer, ForeignKey("units.id"))
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(255))
    phone = Column(String(50))
    lead_source_id = Column(Integer, ForeignKey("lead_sources.id"))
    lead_status = Column(String(30), default="New")
    funnel_stage = Column(String(30), default="Inquiry")
    first_contact_date = Column(DateTime)
    last_contact_date = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class Application(Base):
    __tablename__ = "applications"
    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_org_id = Column(Integer, ForeignKey("tenant_orgs.id"))
    lead_id = Column(Integer, ForeignKey("leads.id"))
    unit_id = Column(Integer, ForeignKey("units.id"))
    tenant_id = Column(Integer, ForeignKey("tenants.id"))
    application_date = Column(Date)
    desired_move_in = Column(Date)
    desired_lease_term = Column(Integer)
    status = Column(String(20), default="Submitted")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class ScreeningResult(Base):
    __tablename__ = "screening_results"
    id = Column(Integer, primary_key=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("applications.id"), nullable=False)
    screening_type = Column(String(30), nullable=False)
    score = Column(Integer)
    result = Column(String(20), default="Pending")
    provider = Column(String(100))
    completed_at = Column(DateTime)
    notes = Column(Text)
    created_at = Column(DateTime, server_default=func.now())

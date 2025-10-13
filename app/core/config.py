import os
from typing import Optional, List
from pydantic import validator, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # Application settings
    app_name: str = Field(default="Describo", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    log_level: str = Field(default="WARNING", alias="LOG_LEVEL")
    frontend_domain: str = Field(alias="FRONTEND_DOMAIN")
    
    # Server settings
    host: str = "0.0.0.0"
    port: int = 5000
    
    # CORS settings
    cors_allow_credentials: bool = True
    cors_allow_methods: List[str] = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    cors_allow_headers: List[str] = [
        "Accept",
        "Accept-Language", 
        "Content-Language",
        "Content-Type",
        "Authorization",
        "X-Requested-With",
        "stripe-signature"
    ]
    allowed_hosts: str = Field(default="192.168.1.134", alias="ALLOWED_HOSTS")

    # Supabase settings
    supabase_url: str = Field(..., alias="SUPABASE_URL")  # Required
    supabase_pub_key: str = Field(..., min_length=32, alias="SUPABASE_PUB_KEY") 
    supabase_secret_key: str = Field(..., min_length=32, alias="SUPABASE_SECRET_KEY")
    
    # OpenRouter/OpenAI settings
    openrouter_api_key: Optional[str] = Field(default=None, alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = Field(default="https://openrouter.ai/api/v1", alias="OPENROUTER_BASE_URL")
    site_title: str = Field(default="Describo", alias="SITE_NAME")


    @model_validator(mode='before')
    @classmethod
    def set_default_frontend_domain(cls, data: dict) -> dict:
        """
        Sets frontend_domain based on the environment if it wasn't already
        defined in the .env file.
        """
        # We only apply our logic if FRONTEND_DOMAIN is NOT in the .env file.
        # Pydantic normalizes keys to lowercase when populating `data`.
        if 'frontend_domain' not in data:
            
            # Use the environment value loaded from .env, or the default "development".
            env_value = data.get('environment', 'development')

            if env_value == 'development':
                data['frontend_domain'] = "http://192.168.1.134:5173"
            else:
                data['frontend_domain'] = "https://www.describo.com"
        
        return data
    
    enable_security_headers: bool = Field(default=True, alias="ENABLE_SECURITY_HEADERS")
    enable_hsts: bool = Field(default=True, alias="ENABLE_HSTS")
    hsts_max_age: int = Field(default=31536000, alias="HSTS_MAX_AGE")  # 1 year
    enable_csp: bool = Field(default=True, alias="ENABLE_CSP")
    csp_report_uri: Optional[str] = Field(default=None, alias="CSP_REPORT_URI")
    
    # Email settings
    gmail_user: Optional[str] = Field(default=None, alias="GMAIL_USER")
    gmail_pass: Optional[str] = Field(default=None, alias="GMAIL_PASS")
    gmail_to: Optional[str] = Field(default=None, alias="GMAIL_TO")
    site_name: str = Field(default="Describo", alias="SITE_NAME")
    
    # Stripe settings
    stripe_secret_key: Optional[str] = Field(default=None, alias="STRIPE_SECRET_KEY")
    stripe_api_key: Optional[str] = Field(default=None, alias="STRIPE_API_KEY")
    stripe_webhook_secret: Optional[str] = Field(default=None, alias="STRIPE_WEBHOOK_SECRET")
    stripe_price_id_maker: Optional[str] = Field(default=None, alias="STRIPE_PRICE_ID_MAKER")
    stripe_price_id_studio: Optional[str] = Field(default=None, alias="STRIPE_PRICE_ID_STUDIO")
    
    
    @validator("supabase_url")
    def validate_supabase_url(cls, v):
        if not v:
            raise ValueError("SUPABASE_URL must be set")
        if not v.startswith("https://"):
            raise ValueError("SUPABASE_URL must use HTTPS")
        return v
    
    @validator("supabase_pub_key")
    def validate_supabase_pub_key(cls, v):
        if not v:
            raise ValueError("SUPABASE_PUB_KEY must be set")
        if len(v) < 30:
            raise ValueError("SUPABASE_PUB_KEY appears to be invalid (too short)")
        return v
    
    @validator("supabase_secret_key")
    def validate_supabase_secret_key(cls, v):
        """Validate supabase secret key"""
        if not v:
            raise ValueError("SUPABASE_SECRET_KEY must be set - this is critical for security")
        if len(v) < 32:
            raise ValueError("SUPABASE_SECRET_KEY must be at least 32 characters for security")
        return v
    
    @property
    def cors_origins(self) -> List[str]:
        """Get CORS origins based on environment"""
        if self.environment == "development":
            return [
                "http://192.168.1.134:5173"
            ]
        else:  # production
            return [
                "https://www.describo.com",
                "https://describo.com"
            ]
    
    @property
    def ALLOWED_HOSTS(self) -> List[str]:
        """Parse ALLOWED_HOSTS from comma-separated string"""
        if isinstance(self.allowed_hosts, str):
            return [host.strip() for host in self.allowed_hosts.split(",") if host.strip()]
        return self.allowed_hosts
    
    
    # # Stripe property methods for backward compatibility
    # @property
    # def STRIPE_SECRET_KEY(self) -> Optional[str]:
    #     """Return Stripe secret key"""
    #     return self.stripe_secret_key
    
    # @property
    # def STRIPE_API_KEY(self) -> Optional[str]:
    #     """Return Stripe publishable key"""
    #     return self.stripe_api_key
    
    # @property
    # def STRIPE_WEBHOOK_SECRET(self) -> Optional[str]:
    #     """Return Stripe webhook secret"""
    #     return self.stripe_webhook_secret
    

    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from environment


# Global settings instance
settings = Settings()
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

# Common models
class SuccessResponse(BaseModel):
    status: str = Field(..., description="Status of the operation")
    message: Optional[str] = Field(None, description="Optional message with additional information")

# Brand Voice schemas
class BrandVoiceRequest(BaseModel):
    brand: str = Field(..., description="The brand name to retrieve voice information for")
    user_id: Optional[str] = Field(None, description="Optional user ID (defaults to authenticated user)")

# Vector Search schemas
class VectorSearchRequest(BaseModel):
    metadata_filter: Dict[str, Any] = Field(default={}, description="Metadata filters to apply")
    text_to_vectorize: str = Field(..., description="Text to search for")
    sort_metric: Optional[str] = Field(None, description="Metric to sort results by")

# Sentiment Setup schemas
class SentimentSetupRequest(BaseModel):
    query: str = Field(..., description="The query to analyze sentiment for")

# Top Content schemas
class TopContentRequest(BaseModel):
    query: str = Field(..., description="Query for content selection")
    topic: str = Field("general", description="Topic for content search")

# Source Content schemas
class SourceContentRequest(BaseModel):
    topic_query: str = Field(..., description="Topic to retrieve source content for")

# Repurpose schemas
class RepurposeRequest(BaseModel):
    topic_query: str = Field(..., description="Topic to search for")
    brand: str = Field(..., description="Brand name for content style")
    repurpose_count: int = Field(1, description="Number of repurposed content items to generate")
    workflow_id: str = Field("Legacy Generation Flow", description="ID of workflow to use")

# Top Content Repurposing schemas
class TopContentRepurposingRequest(BaseModel):
    query: str = Field(..., description="Query for content selection")
    topic: str = Field(..., description="Topic for content search")
    brand: str = Field(..., description="Brand name for content style")
    number_of_posts: int = Field(5, description="Number of posts to select")
    repurpose_count: int = Field(5, description="Number of repurposed items to generate")
    workflow_id: str = Field("Legacy Generation Flow", description="ID of workflow to use")

# Social Post Generation schemas
class SocialPostGenerationRequest(BaseModel):
    workflow_id: str = Field(..., description="ID of workflow to use")
    client_brief: str = Field(..., description="Client brief for post generation")
    template: str = Field(..., description="Template to use for post")
    content_chunks: str = Field(..., description="Content chunks to use in generation")
    brand_voice: str = Field("", description="Brand voice guidelines")

class SocialPostGenerationResponse(BaseModel):
    generated_content: str = Field(..., description="Generated social post content")

# Template Context schemas
class TemplateContextRequest(BaseModel):
    template: str = Field(..., description="Template to create embedding for")
    template_id: Optional[str] = Field(None, description="Optional template ID for updates")
    description: Optional[str] = Field(None, description="Optional pre-defined description")

# Content Upload schemas
class ContentUploadRequest(BaseModel):
    content_data: Dict[str, Any] = Field(..., description="Content data to upload")

# Flow Config schemas
class FlowConfigResponse(BaseModel):
    workflow_id: str = Field(..., description="Workflow ID")
    flow_config: Dict[str, Any] = Field(..., description="Flow configuration")

# Templatizer schemas
class TemplatizerRequest(BaseModel):
    social_post: str = Field(..., description="Social post to templatize")

class TemplatizerResponse(BaseModel):
    template: str = Field(..., description="Generated template")

# Multitemplate schemas
class MultitemplateRequest(BaseModel):
    content_chunk: str = Field(..., description="Content chunk to find templates for")
    template_count: int = Field(5, description="Number of templates to retrieve")
    db_to_access: str = Field("sys", description="Which databases to access ('sys', 'user', or 'both')")
    category: str = Field("Short Form", description="Template category to filter by ('Short Form', 'Atomic', or 'Mid Form')")

# Repurpose with Templates schemas
class RepurposeWithTemplatesRequest(BaseModel):
    content_chunks: str = Field(..., description="Content chunks to repurpose")
    template_post: str = Field(..., description="Template post to use")
    brand: str = Field(..., description="Brand name for content style")
    workflow_id: str = Field("Legacy Generation Flow", description="Workflow ID to use")
    is_given_template_query: bool = Field(False, description="Whether the template is a query")
    number_of_posts_to_template: int = Field(5, description="Number of posts to template")
    post_topic_query: str = Field("Digital Operations", description="Topic query for posts")

# Source Content Repurpose with Templates schemas
class SourceContentRepurposeWithTemplatesRequest(BaseModel):
    content_topic_query: str = Field(..., description="Topic query for content")
    template_post: str = Field(..., description="Template post to use")
    brand: str = Field(..., description="Brand name for content style")
    workflow_id: str = Field("Legacy Generation Flow", description="Workflow ID to use")
    is_given_template_query: bool = Field(False, description="Whether the template is a query")
    number_of_posts_to_template: int = Field(5, description="Number of posts to template")
    post_topic_query: str = Field("Digital Operations", description="Topic query for posts")

# Generation Flow schemas
class MessageItem(BaseModel):
    role: str = Field(..., description="Role of the message sender (e.g., 'system', 'user', 'assistant')")
    content: str = Field(..., description="Content of the message")

class GenerationStep(BaseModel):
    Order: int = Field(..., description="Step order in the workflow")
    Step_name: str = Field(..., description="Name of the step")
    Model: str = Field(..., description="AI model to use")
    System_prompt: str = Field(..., description="System prompt for the model")
    Message: List[MessageItem] = Field(..., description="Message objects with role and content")
    Max_tokens: int = Field(..., description="Maximum tokens for generation")
    Temperature: float = Field(..., description="Temperature for generation")

class GenerationFlowRequest(BaseModel):
    workflowId: str = Field(..., description="Unique identifier for the workflow")
    workflowType: str = Field(..., description="Type of workflow")
    description: str = Field(..., description="Short description of the workflow")
    workflow_name: Optional[str] = Field(None, description="Display name for the workflow")
    steps: List[GenerationStep] = Field(..., description="Workflow generation steps")

# Content Upload
class ContentUploadRequest(BaseModel):
    first_draft: str = Field(..., description="First draft of the content")
    content_chunks: str = Field(..., description="Source content chunks")
    template: str = Field(..., description="Template used for generation")
    template_id: Optional[str] = Field(None, description="ID reference to system templates")
    brand_id: Optional[str] = Field(None, description="ID reference to brand used")
    workflow_id: Optional[str] = Field("Legacy Generation Flow", description="ID of workflow used for generation")
    workflow_name: Optional[str] = Field("Legacy Generation Flow", description="Name of the workflow used")
    content_format: Optional[str] = Field("Short Form Social", description="Format of the content")
    post_id: Optional[str] = Field(None, description="UUID for the post (generates automatically if not provided)")
    current_draft: Optional[str] = Field("", description="Current version of the content")
    status: Optional[str] = Field("Draft", description="Status of the content")
    metrics: Optional[Dict[str, int]] = Field(None, description="Engagement metrics")

# Source Content
class SourceContentRequest(BaseModel):
    topic_query: str = Field(..., description="Topic to search for in source content")

# Top Content Repurposing
class TopContentRepurposingRequest(BaseModel):
    query: str = Field(..., description="Query for content selection")
    topic: str = Field(..., description="Topic for content search")
    brand: str = Field(..., description="Brand name for content style")
    number_of_posts: int = Field(5, description="Number of posts to select")
    repurpose_count: int = Field(5, description="Number of repurposed items to generate")
    workflow_id: str = Field("Legacy Generation Flow", description="ID of workflow to use")

# Template Context
class TemplateContextRequest(BaseModel):
    template: str = Field(..., description="Template to process and embed")

# Templatizer
class TemplatizerRequest(BaseModel):
    social_post: str = Field(..., description="Social post to convert to template")

class TemplatizerResponse(BaseModel):
    template: str = Field(..., description="Generated template")

# Multitemplate
class MultitemplateRequest(BaseModel):
    content_chunk: str = Field(..., description="Content chunk to find templates for")
    template_count: int = Field(5, description="Number of templates to retrieve")

# Repurpose with Templates
class RepurposeWithTemplatesRequest(BaseModel):
    content_chunks: str = Field(..., description="Content chunks to repurpose")
    template_post: str = Field(..., description="Template post to use")
    brand: str = Field(..., description="Brand name for content style")
    workflow_id: str = Field("Legacy Generation Flow", description="Workflow ID to use")
    is_given_template_query: bool = Field(False, description="Whether the template is a query")
    number_of_posts_to_template: int = Field(5, description="Number of posts to template")
    post_topic_query: str = Field("Digital Operations", description="Topic query for posts")

# Source Content Repurpose with Templates
class SourceContentRepurposeWithTemplatesRequest(BaseModel):
    content_topic_query: str = Field(..., description="Topic query for source content")
    template_post: str = Field(..., description="Template post to use")
    brand: str = Field(..., description="Brand name for content style")
    workflow_id: str = Field("Legacy Generation Flow", description="Workflow ID to use")
    is_given_template_query: bool = Field(False, description="Whether the template is a query")
    number_of_posts_to_template: int = Field(5, description="Number of posts to template")
    post_topic_query: str = Field("Digital Operations", description="Topic query for posts")

# Simple Repurpose Request
class SimpleRepurposeRequest(BaseModel):
    social_post: str = Field(..., description="Social post to repurpose")
    brand: str = Field(..., description="Brand name for content style")
    repurpose_count: int = Field(5, description="Number of templates to use")
    workflow_id: str = Field("Simple Repurpose Flow", description="ID of workflow to use")

# API Key schemas
class ApiKeyCreateRequest(BaseModel):
    name: str = Field(..., description="Descriptive name for the API key")
    scope: str = Field("user", description="Permission scope (admin or user)")

class ApiKeyResponse(BaseModel):
    api_key: str = Field(..., description="Full API key (only shown once)")
    prefix: str = Field(..., description="API key prefix for display")
    name: str = Field(..., description="Descriptive name")
    scope: str = Field(..., description="Permission scope")
    created_at: str = Field(..., description="Creation timestamp")
    is_active: bool = Field(..., description="Whether the key is active")
    id: str = Field(..., description="Database ID")

class ApiKeyInfo(BaseModel):
    id: str = Field(..., description="Database ID")
    name: str = Field(..., description="Descriptive name")
    prefix: str = Field(..., description="API key prefix for display")
    scope: str = Field(..., description="Permission scope")
    created_at: str = Field(..., description="Creation timestamp")
    last_used: Optional[str] = Field(None, description="Last used timestamp")
    is_active: bool = Field(..., description="Whether the key is active")

class ApiKeyListResponse(BaseModel):
    keys: list[ApiKeyInfo] = Field(..., description="List of API keys")
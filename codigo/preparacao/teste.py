
from google import genai

client = genai.Client(
    api_key="AQ.Ab8RN6JfMxV2WrAVLooCvjTixYQZqcpfwlGR6X8D3bmtJL4hRw"
)

response = client.models.generate_content(
    model="gemini-3.5-flash",
    contents="Olá"
)

print(response.text)
import os
from typing import Optional

# from pydantic import BaseModel, Field
import serpapi
from langchain.pydantic_v1 import BaseModel, Field
from langchain_core.tools import tool

from agents.tools.serpapi_utils import safe_serpapi_error


class FlightsInput(BaseModel):
    departure_airport: Optional[str] = Field(description='Departure airport code (IATA)')
    arrival_airport: Optional[str] = Field(description='Arrival airport code (IATA)')
    outbound_date: Optional[str] = Field(description='Parameter defines the outbound date. The format is YYYY-MM-DD. e.g. 2024-06-22')
    return_date: Optional[str] = Field(description='Parameter defines the return date. The format is YYYY-MM-DD. e.g. 2024-06-28')
    adults: Optional[int] = Field(1, description='Parameter defines the number of adults. Default to 1.')
    children: Optional[int] = Field(0, description='Parameter defines the number of children. Default to 0.')
    infants_in_seat: Optional[int] = Field(0, description='Parameter defines the number of infants in seat. Default to 0.')
    infants_on_lap: Optional[int] = Field(0, description='Parameter defines the number of infants on lap. Default to 0.')


class FlightsInputSchema(BaseModel):
    params: FlightsInput


def _public_flight(flight):
    return {
        key: value for key, value in flight.items()
        if key not in ('departure_token', 'booking_token')
    }


@tool(args_schema=FlightsInputSchema)
def flights_finder(params: FlightsInput):
    '''
    Find flights using the Google Flights engine.

    Returns:
        dict: Flight search results.
    '''

    params = {
        'api_key': os.environ.get('SERPAPI_API_KEY'),
        'engine': 'google_flights',
        'hl': 'en',
        'gl': 'us',
        'departure_id': params.departure_airport,
        'arrival_id': params.arrival_airport,
        'outbound_date': params.outbound_date,
        'return_date': params.return_date,
        'currency': 'USD',
        'adults': params.adults,
        'infants_in_seat': params.infants_in_seat,
        'stops': '1',
        'infants_on_lap': params.infants_on_lap,
        'children': params.children
    }

    try:
        search = serpapi.search(params)
        outbound_options = search.data.get('best_flights', [])
        if len(outbound_options) < 3:
            outbound_options = outbound_options + search.data.get('other_flights', [])
        outbound_options = outbound_options[:3]
        if not outbound_options:
            return {'error': 'SerpAPI returned no outbound flight options.'}

        if not params['return_date']:
            return {'outbound_flights': [_public_flight(flight) for flight in outbound_options]}

        trip_options = []
        for outbound_flight in outbound_options:
            departure_token = outbound_flight.get('departure_token')
            if not departure_token:
                trip_options.append({
                    'outbound_flight': _public_flight(outbound_flight),
                    'return_flights': [],
                    'warning': 'No departure token was provided for this outbound flight.',
                })
                continue

            return_params = {**params, 'departure_token': departure_token}
            return_search = serpapi.search(return_params)
            return_flights = return_search.data.get('best_flights', [])
            if not return_flights:
                return_flights = return_search.data.get('other_flights', [])

            trip_options.append({
                'outbound_flight': _public_flight(outbound_flight),
                'return_flights': [_public_flight(flight) for flight in return_flights[:3]],
            })

        return {'trip_options': trip_options}
    except Exception as e:
        return safe_serpapi_error(e)
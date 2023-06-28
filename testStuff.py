import requests

def oauth(r):
    r.headers["Authorization"] = 'Bearer ' + 'AAAAAAAAAAAAAAAAAAAAAK8OcgEAAAAANxL2pfyl2jApzpOCiNfcysnK%2BPE%3DkcbTF6AjV1oKPcPA4NAfM650YVJD0bHCS2wYp12WcC3VmYSFRC'
    return r

def get_following(user_id):
    url = "https://api.twitter.com/2/users/{}/following".format(user_id)
    params = {'max_results': 100, 'user.fields': 'id,name,username,public_metrics'}
    all_followings = []

    while True:
        response = requests.get(url, params=params, auth=oauth)
        if response.status_code != 200:
            raise Exception(response.status_code, response.text)
        data = response.json()
        all_followings.extend(data['data'])
        if 'next_token' in data['meta']:
            params['pagination_token'] = data['meta']['next_token']
        else:
            break

    return all_followings

def main():
    user_id = '4646461997'
    json_response = get_following(user_id)
    data = json_response
    print(data)

if __name__ == "__main__":
    main()
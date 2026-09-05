from alpha_poker_api.ratings import BASE_RATING, calculate_round_robin_elo, expected_score


def test_equal_players_have_an_even_expected_score():
    assert expected_score(1200, 1200) == 0.5
    assert expected_score(1400, 1200) > 0.5


def test_round_robin_elo_and_records_are_order_independent():
    starts = {"alpha": BASE_RATING, "beta": BASE_RATING, "gamma": BASE_RATING}
    results = [
        ("alpha", "beta", 1.0),
        ("alpha", "gamma", 1.0),
        ("beta", "gamma", 1.0),
    ]
    standings = calculate_round_robin_elo(starts, results)
    reversed_standings = calculate_round_robin_elo(starts, reversed(results))

    assert standings == reversed_standings
    assert standings["alpha"].rating == 1232
    assert standings["alpha"].wins == 2
    assert standings["alpha"].losses == 0
    assert standings["beta"].rating == 1200
    assert standings["beta"].wins == standings["beta"].losses == 1
    assert standings["gamma"].rating == 1168
    assert sum(standing.rating for standing in standings.values()) == 3 * BASE_RATING


def test_draws_preserve_equal_ratings():
    standings = calculate_round_robin_elo(
        {"left": BASE_RATING, "right": BASE_RATING},
        [("left", "right", 0.5)],
    )
    assert standings["left"].rating == standings["right"].rating == BASE_RATING
    assert standings["left"].draws == standings["right"].draws == 1

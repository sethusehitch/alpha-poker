from alpha_poker_api.ratings import (
    BASE_RATING, ESTABLISHED_K_FACTOR, PROVISIONAL_K_FACTOR,
    calculate_elo_result, calculate_round_robin_elo, expected_score, k_factor,
)


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


def test_chess_style_result_uses_provisional_then_established_k_factor():
    assert k_factor(0) == k_factor(9) == PROVISIONAL_K_FACTOR
    assert k_factor(10) == ESTABLISHED_K_FACTOR
    provisional = calculate_elo_result(1200, 1200, 1.0)
    established = calculate_elo_result(
        1200, 1200, 1.0, rated_matches_a=10, rated_matches_b=10
    )
    assert provisional == (1220, 1180, 40, 40)
    assert established == (1210, 1190, 20, 20)


def test_mixed_experience_uses_each_players_chess_k_factor():
    after_a, after_b, ka, kb = calculate_elo_result(
        1200, 1200, 1.0, rated_matches_a=0, rated_matches_b=10
    )
    assert (after_a, after_b, ka, kb) == (1220, 1190, 40, 20)


def test_expected_win_moves_rating_less_than_an_upset():
    expected_winner = calculate_elo_result(1600, 1200, 1.0)[0] - 1600
    upset_winner = calculate_elo_result(1200, 1600, 1.0)[0] - 1200
    assert 0 < expected_winner < upset_winner
